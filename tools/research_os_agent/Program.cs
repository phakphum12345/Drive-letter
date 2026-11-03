using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

const string ServiceName = "ResearchOSLocalAgent";

if (args.Any(arg => string.Equals(arg, "--configure", StringComparison.OrdinalIgnoreCase)))
{
    AgentConfiguration.ConfigureInteractive();
    return;
}

var host = Host.CreateDefaultBuilder(args)
    .UseWindowsService(options => options.ServiceName = ServiceName)
    .ConfigureServices(services => services.AddHostedService<LocalAgentWorker>())
    .Build();

await host.RunAsync();

sealed class LocalAgentWorker : BackgroundService
{
    private readonly ILogger<LocalAgentWorker> _logger;
    private readonly HttpClient _http = new();
    private AgentConfiguration? _configuration;
    private LocalAgentApiClient? _api;
    private List<AgentCapability> _capabilities = [];

    public LocalAgentWorker(ILogger<LocalAgentWorker> logger) => _logger = logger;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _configuration = AgentConfiguration.Load();
        if (_configuration is null)
        {
            _logger.LogError("Agent configuration is missing. Run ResearchOS.LocalAgent.exe --configure as Administrator.");
            return;
        }

        if (!AgentConfiguration.IsAllowedApiUrl(_configuration.ApiBaseUrl))
        {
            _logger.LogCritical("Agent API URL must use HTTPS, except for localhost development.");
            return;
        }

        _api = new LocalAgentApiClient(_http, _configuration.ApiBaseUrl);
        _capabilities = Directory.Exists(_configuration.WorkspaceRoot)
            ? [new AgentCapability("repository.inspect", "1")]
            : [];

        try
        {
            if (string.IsNullOrWhiteSpace(_configuration.AgentToken))
            {
                if (string.IsNullOrWhiteSpace(_configuration.EnrollmentToken))
                {
                    _logger.LogCritical("No Agent token or enrollment grant is configured. Reconfigure the Agent.");
                    return;
                }

                var token = await _api.EnrollAsync(_configuration, _capabilities, stoppingToken);
                _configuration.AgentToken = token;
                _configuration.EnrollmentToken = null;
                AgentConfiguration.Save(_configuration);
                _logger.LogInformation("Local Agent enrollment completed; bearer credential was stored with Windows DPAPI.");
            }

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await _api.HeartbeatAsync(_configuration.AgentToken!, _capabilities, stoppingToken);
                    var job = await _api.ClaimAsync(_configuration.AgentToken!, stoppingToken);
                    if (job is not null)
                    {
                        await ProcessJobAsync(job, stoppingToken);
                    }

                    await Task.Delay(TimeSpan.FromSeconds(15), stoppingToken);
                }
                catch (UnauthorizedAccessException)
                {
                    _logger.LogCritical("Agent credential was rejected or revoked. Service stopped; a new owner enrollment grant is required.");
                    return;
                }
                catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
                {
                    return;
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Cloud + Local API is temporarily unavailable; retrying without discarding the Agent credential.");
                    await Task.Delay(TimeSpan.FromSeconds(15), stoppingToken);
                }
            }
        }
        finally
        {
            _http.Dispose();
        }
    }

    private async Task ProcessJobAsync(CloudLocalJob job, CancellationToken cancellationToken)
    {
        if (_api is null || _configuration is null || string.IsNullOrWhiteSpace(_configuration.AgentToken))
            return;

        try
        {
            await _api.TransitionAsync(job, _configuration.AgentToken!, "RUNNING", "agent.dispatch", [], cancellationToken);

            if (!string.Equals(job.TaskType, "repo.audit", StringComparison.Ordinal))
                throw new InvalidOperationException("unsupported_task_type");

            if (string.IsNullOrWhiteSpace(_configuration.WorkspaceRoot))
                throw new InvalidOperationException("workspace_root_not_configured");

            var artifactHash = await GitRepositoryAuditor.AuditAsync(
                _configuration.WorkspaceRoot, job.SourceSha, cancellationToken);

            // The API commits the state transition and lifecycle evidence in one DB transaction.
            await _api.TransitionAsync(job, _configuration.AgentToken!, "COMPLETED", "repo.audit", [artifactHash], cancellationToken);
            _logger.LogInformation("Read-only repository audit completed for job {JobId}.", job.JobId);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Local job {JobId} failed safely; no arbitrary command was executed.", job.JobId);
            try
            {
                await _api.TransitionAsync(job, _configuration.AgentToken!, "FAILED", "agent.failure", [], cancellationToken);
            }
            catch (Exception transitionError)
            {
                _logger.LogWarning(transitionError, "Could not persist failed transition for job {JobId}; lease recovery is required.", job.JobId);
            }
        }
    }
}

sealed class LocalAgentApiClient
{
    private readonly HttpClient _http;
    private readonly Uri _baseUri;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };

    public LocalAgentApiClient(HttpClient http, string baseUrl)
    {
        _http = http;
        _baseUri = new Uri(baseUrl.TrimEnd('/') + "/", UriKind.Absolute);
        _http.Timeout = TimeSpan.FromSeconds(20);
    }

    public async Task<string> EnrollAsync(AgentConfiguration config, List<AgentCapability> capabilities, CancellationToken ct)
    {
        using var response = await PostAsync("api/v1/agents/enroll", new
        {
            enrollment_token = config.EnrollmentToken,
            device_id = config.DeviceId,
            protocol_versions = new[] { "1.0" },
            capabilities,
            os_name = "Windows",
            os_version = Environment.OSVersion.VersionString,
            agent_version = "1.0.0"
        }, null, ct);

        var token = response.RootElement.GetProperty("agent_token").GetString();
        if (string.IsNullOrWhiteSpace(token))
            throw new InvalidOperationException("agent_token_missing_from_enrollment_response");
        return token;
    }

    public async Task HeartbeatAsync(string token, List<AgentCapability> capabilities, CancellationToken ct)
    {
        using var response = await PostAsync("api/v1/agents/heartbeat", new { capabilities }, token, ct);
    }

    public async Task<CloudLocalJob?> ClaimAsync(string token, CancellationToken ct)
    {
        using var response = await PostAsync("api/v1/agents/claim", new { lease_seconds = 120 }, token, ct);
        var job = response.RootElement.GetProperty("job");
        return job.ValueKind == JsonValueKind.Object
            ? JsonSerializer.Deserialize<CloudLocalJob>(job.GetRawText(), JsonOptions)
            : null;
    }

    public async Task TransitionAsync(CloudLocalJob job, string agentToken, string status, string stageId,
        string[] artifactHashes, CancellationToken ct)
    {
        using var response = await PostAsync(
            "api/v1/jobs/" + Uri.EscapeDataString(job.JobId) + "/transition",
            new
            {
                lease_token = job.LeaseToken,
                status,
                stage_id = stageId,
                artifact_hashes = artifactHashes
            },
            agentToken,
            ct);
    }

    private async Task<JsonDocument> PostAsync(string path, object body, string? bearerToken,
        CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, new Uri(_baseUri, path));
        request.Content = JsonContent.Create(body);
        if (!string.IsNullOrWhiteSpace(bearerToken))
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", bearerToken);

        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
            throw new UnauthorizedAccessException("Agent API rejected the credential.");
        if (response.StatusCode == HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("Agent API denied this operation.");
        if (!response.IsSuccessStatusCode)
        {
            var detail = await response.Content.ReadAsStringAsync(ct);
            throw new HttpRequestException("Agent API returned " + (int)response.StatusCode + ": " + detail,
                null, response.StatusCode);
        }

        return await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(ct), cancellationToken: ct);
    }
}

sealed class CloudLocalJob
{
    [JsonPropertyName("job_id")] public string JobId { get; set; } = "";
    [JsonPropertyName("task_type")] public string TaskType { get; set; } = "";
    [JsonPropertyName("source_sha")] public string SourceSha { get; set; } = "";
    [JsonPropertyName("lease_token")] public string LeaseToken { get; set; } = "";
}

sealed record AgentCapability(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("version")] string Version);

static class GitRepositoryAuditor
{
    public static async Task<string> AuditAsync(string workspaceRoot, string expectedSha, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(expectedSha))
            throw new InvalidOperationException("source_sha_required");

        var root = Path.GetFullPath(workspaceRoot);
        if (!Directory.Exists(root))
            throw new DirectoryNotFoundException("configured_workspace_not_found");

        var actualRoot = (await RunGitAsync(root, ["rev-parse", "--show-toplevel"], ct)).Trim();
        if (!string.Equals(Path.GetFullPath(actualRoot), root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("workspace_root_must_be_the_git_root");

        var head = (await RunGitAsync(root, ["rev-parse", "HEAD"], ct)).Trim();
        if (!string.Equals(head, expectedSha, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("source_sha_mismatch");

        // File names and file contents never leave the PC. Only a hash of the
        // read-only status summary is sent as evidence.
        var status = await RunGitAsync(root, ["status", "--porcelain", "--untracked-files=no"], ct);
        var digest = SHA256.HashData(Encoding.UTF8.GetBytes(head + "\n" + status));
        return Convert.ToHexString(digest).ToLowerInvariant();
    }

    private static async Task<string> RunGitAsync(string root, string[] arguments, CancellationToken ct)
    {
        var start = new ProcessStartInfo
        {
            FileName = "git",
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        foreach (var argument in arguments)
            start.ArgumentList.Add(argument);

        using var process = new Process { StartInfo = start };
        if (!process.Start())
            throw new InvalidOperationException("git_process_start_failed");

        var stdoutTask = process.StandardOutput.ReadToEndAsync(ct);
        var stderrTask = process.StandardError.ReadToEndAsync(ct);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
        timeout.CancelAfter(TimeSpan.FromSeconds(12));

        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(entireProcessTree: true); } catch { }
            throw;
        }

        var stdout = await stdoutTask;
        var stderr = await stderrTask;
        if (process.ExitCode != 0)
            throw new InvalidOperationException("git_read_only_audit_failed: " + stderr.Trim());
        return stdout;
    }
}

sealed class AgentConfiguration
{
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("ResearchOS.LocalAgent.Config.v1");
    public string ApiBaseUrl { get; set; } = "";
    public string? EnrollmentToken { get; set; }
    public string? AgentToken { get; set; }
    public string DeviceId { get; set; } = "";
    public string WorkspaceRoot { get; set; } = "";

    public static string DataDirectory =>
        Environment.GetEnvironmentVariable("RESEARCH_OS_AGENT_DATA_DIR")
        ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "ResearchOSAgent");

    private static string ConfigPath => Path.Combine(DataDirectory, "agent-config.dpapi");
    private static string DevicePath => Path.Combine(DataDirectory, "device-id.txt");

    public static bool IsAllowedApiUrl(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri))
            return false;
        return uri.Scheme == Uri.UriSchemeHttps
            || (uri.Scheme == Uri.UriSchemeHttp && (uri.IsLoopback || uri.Host.Equals("localhost", StringComparison.OrdinalIgnoreCase)));
    }

    public static AgentConfiguration? Load()
    {
        if (!File.Exists(ConfigPath))
            return null;
        var encrypted = File.ReadAllBytes(ConfigPath);
        var clear = ProtectedData.Unprotect(encrypted, Entropy, DataProtectionScope.LocalMachine);
        return JsonSerializer.Deserialize<AgentConfiguration>(clear);
    }

    public static void Save(AgentConfiguration config)
    {
        Directory.CreateDirectory(DataDirectory);
        var clear = JsonSerializer.SerializeToUtf8Bytes(config);
        var encrypted = ProtectedData.Protect(clear, Entropy, DataProtectionScope.LocalMachine);
        var temp = ConfigPath + ".tmp";
        File.WriteAllBytes(temp, encrypted);
        File.Move(temp, ConfigPath, overwrite: true);
    }

    public static void ConfigureInteractive()
    {
        Console.WriteLine("Research OS Local Agent — secure configuration");
        Console.Write("Research OS API base URL (HTTPS): ");
        var apiUrl = Console.ReadLine()?.Trim() ?? "";
        if (!IsAllowedApiUrl(apiUrl))
            throw new InvalidOperationException("API URL must use HTTPS, except localhost development.");

        Console.Write("One-time enrollment grant (input hidden): ");
        var grant = ReadSecret();
        if (string.IsNullOrWhiteSpace(grant))
            throw new InvalidOperationException("Enrollment grant is required.");

        Console.Write("Local Git repository root (optional): ");
        var workspace = Console.ReadLine()?.Trim() ?? "";
        if (!string.IsNullOrWhiteSpace(workspace) && !Directory.Exists(workspace))
            throw new DirectoryNotFoundException("Configured workspace does not exist.");

        Directory.CreateDirectory(DataDirectory);
        var deviceId = File.Exists(DevicePath) ? File.ReadAllText(DevicePath).Trim() : "windows-" + Guid.NewGuid().ToString("N");
        File.WriteAllText(DevicePath, deviceId);

        Save(new AgentConfiguration
        {
            ApiBaseUrl = apiUrl.TrimEnd('/'),
            EnrollmentToken = grant,
            DeviceId = deviceId,
            WorkspaceRoot = string.IsNullOrWhiteSpace(workspace) ? "" : Path.GetFullPath(workspace)
        });

        Console.WriteLine("Configuration saved using Windows DPAPI (LocalMachine). No credential was written in plaintext.");
        TryStartService();
    }

    private static string ReadSecret()
    {
        var value = new StringBuilder();
        while (true)
        {
            var key = Console.ReadKey(intercept: true);
            if (key.Key == ConsoleKey.Enter)
            {
                Console.WriteLine();
                break;
            }
            if (key.Key == ConsoleKey.Backspace)
            {
                if (value.Length > 0) value.Length--;
                continue;
            }
            if (!char.IsControl(key.KeyChar))
                value.Append(key.KeyChar);
        }
        return value.ToString();
    }

    private static void TryStartService()
    {
        try
        {
            var query = RunSc(["query", "ResearchOSLocalAgent"]);
            if (query.ExitCode != 0)
            {
                Console.WriteLine("Agent service is not installed. Run scripts\\research-os-agent-service.ps1 -Action install first.");
                return;
            }
            RunSc(["config", "ResearchOSLocalAgent", "start=", "delayed-auto"]);
            var start = RunSc(["start", "ResearchOSLocalAgent"]);
            Console.WriteLine(start.ExitCode == 0 ? "Local Agent service start requested." : "Configuration saved; start the service from an elevated PowerShell window.");
        }
        catch
        {
            Console.WriteLine("Configuration saved. Start the Local Agent service from an elevated PowerShell window.");
        }
    }

    private static (int ExitCode, string Output) RunSc(string[] args)
    {
        var start = new ProcessStartInfo { FileName = "sc.exe", UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in args) start.ArgumentList.Add(argument);
        using var process = Process.Start(start) ?? throw new InvalidOperationException("sc.exe unavailable");
        var output = process.StandardOutput.ReadToEnd() + process.StandardError.ReadToEnd();
        process.WaitForExit(10000);
        return (process.ExitCode, output);
    }
}
