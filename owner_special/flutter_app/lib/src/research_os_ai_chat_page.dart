import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'owner_api.dart';

enum _ChatMode { balanced, research, analysis, planning }

extension on _ChatMode {
  String get label => switch (this) {
        _ChatMode.balanced => 'Balanced',
        _ChatMode.research => 'Research',
        _ChatMode.analysis => 'Deep analysis',
        _ChatMode.planning => 'Planning',
      };

  String get description => switch (this) {
        _ChatMode.balanced => 'ตอบคำถามทั่วไปและช่วยทำงาน',
        _ChatMode.research => 'ค้นคว้าและสังเคราะห์ข้อมูล',
        _ChatMode.analysis => 'วิเคราะห์เชิงลึกและตรวจสอบเหตุผล',
        _ChatMode.planning => 'วางแผนงานและแบ่งขั้นตอน',
      };

  int get complexity => switch (this) {
        _ChatMode.balanced => 4,
        _ChatMode.research => 6,
        _ChatMode.analysis => 8,
        _ChatMode.planning => 6,
      };

  int get risk => this == _ChatMode.analysis ? 4 : 2;

  List<String> get skills => switch (this) {
        _ChatMode.balanced => const ['analysis', 'planning', 'memory', 'quality'],
        _ChatMode.research => const ['research', 'analysis', 'memory', 'quality'],
        _ChatMode.analysis => const ['analysis', 'verification', 'quality', 'memory'],
        _ChatMode.planning => const ['planning', 'tasks', 'analysis', 'memory'],
      };
}

class ResearchOsAiChatPage extends StatefulWidget {
  const ResearchOsAiChatPage({required this.api, required this.teamName, super.key});

  final OwnerFriendApi api;
  final String teamName;

  @override
  State<ResearchOsAiChatPage> createState() => _ResearchOsAiChatPageState();
}

class _ResearchOsAiChatPageState extends State<ResearchOsAiChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_ChatTurn> _messages = [];
  final List<_ChatSession> _history = [];
  _ChatMode _mode = _ChatMode.balanced;
  bool _busy = false;
  bool _turbo = true;
  String _context = '';
  String _status = 'พร้อมใช้งาน';
  String _brainScale = '-';
  int _capacity = 0;
  int _workers = 0;
  int _batches = 0;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send([String? suggested]) async {
    final question = (suggested ?? _input.text).trim();
    if (question.isEmpty || _busy) return;
    _input.clear();
    final prompt = _context.isEmpty
        ? question
        : 'บริบทเพิ่มเติม:\n$_context\n\nคำถาม:\n$question';
    setState(() {
      _busy = true;
      _status = 'กำลังประมวลผล';
      _messages.add(_ChatTurn(role: 'user', text: question, createdAt: DateTime.now()));
      _context = '';
    });
    await _scrollToEnd();
    try {
      final response = await widget.api.chat(
        prompt,
        complexity: _mode.complexity,
        risk: _mode.risk,
        parallelism: 8,
        helperBudget: _turbo ? 1000000 : 0,
        requestedSkills: _mode.skills,
      );
      final decision = Map<String, dynamic>.from(response['decision'] as Map? ?? const {});
      final helpers = Map<String, dynamic>.from(response['helpers'] as Map? ?? const {});
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatTurn(
          role: 'assistant',
          text: response['text']?.toString() ?? 'ระบบไม่ได้ส่งข้อความตอบกลับ',
          createdAt: DateTime.now(),
        ));
        _brainScale = decision['scale']?.toString() ?? '-';
        _capacity = (decision['capacity'] as num?)?.toInt() ?? 0;
        _workers = (helpers['active_workers'] as num?)?.toInt() ?? 0;
        _batches = (helpers['batches'] as num?)?.toInt() ?? 0;
        _status = 'ตอบกลับแล้ว';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatTurn(
          role: 'assistant',
          text: 'เชื่อมต่อ AI ไม่สำเร็จ\n$error',
          createdAt: DateTime.now(),
          isError: true,
        ));
        _status = 'เชื่อมต่อไม่สำเร็จ';
      });
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        await _scrollToEnd();
      }
    }
  }

  Future<void> _scrollToEnd() async {
    await Future<void>.delayed(const Duration(milliseconds: 60));
    if (_scroll.hasClients) {
      await _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    }
  }

  void _newChat() {
    if (_messages.isNotEmpty) {
      _history.insert(0, _ChatSession(
        title: _messages.firstWhere((m) => m.role == 'user', orElse: () => _messages.first).text,
        messages: List<_ChatTurn>.of(_messages),
        createdAt: DateTime.now(),
      ));
    }
    setState(() {
      _messages.clear();
      _status = 'เริ่มบทสนทนาใหม่';
      _brainScale = '-';
      _capacity = 0;
      _workers = 0;
      _batches = 0;
    });
  }

  Future<void> _showHistory() async {
    final selected = await showModalBottomSheet<_ChatSession>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: 460,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: Text('ประวัติการสนทนา', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              ),
              Expanded(
                child: _history.isEmpty
                    ? const Center(child: Text('ยังไม่มีประวัติในเซสชันนี้'))
                    : ListView.builder(
                        itemCount: _history.length,
                        itemBuilder: (context, index) {
                          final item = _history[index];
                          return ListTile(
                            leading: const CircleAvatar(child: Icon(Icons.chat_bubble_outline)),
                            title: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                            subtitle: Text('${item.messages.length} ข้อความ • ${_time(item.createdAt)}'),
                            onTap: () => Navigator.pop(context, item),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
    if (selected == null || !mounted) return;
    setState(() {
      if (_messages.isNotEmpty) {
        _history.insert(0, _ChatSession(title: _messages.first.text, messages: List.of(_messages), createdAt: DateTime.now()));
      }
      _messages
        ..clear()
        ..addAll(selected.messages);
      _history.remove(selected);
      _status = 'เปิดประวัติแล้ว';
    });
    await _scrollToEnd();
  }

  Future<void> _addContext() async {
    final result = await showDialog<String>(
      context: context,
      builder: (context) => _ContextDialog(initialText: _context),
    );
    if (result != null && mounted) {
      setState(() => _context = result);
    }
  }

  Future<void> _copy(String value) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('คัดลอกคำตอบแล้ว')));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _topBar(theme),
        const SizedBox(height: 12),
        Expanded(
          child: Card(
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                Expanded(
                  child: _messages.isEmpty ? _welcome(theme) : _conversation(theme),
                ),
                if (_busy)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(20, 0, 20, 10),
                    child: Row(children: [
                      SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                      SizedBox(width: 10),
                      Text('Research OS กำลังคิด...'),
                    ]),
                  ),
                _composer(theme),
              ],
            ),
          ),
        ),
        const SizedBox(height: 9),
        _metrics(theme),
      ],
    );
  }

  Widget _topBar(ThemeData theme) {
    final colors = theme.colorScheme;
    return Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [colors.primary, colors.tertiary]),
            borderRadius: BorderRadius.circular(13),
          ),
          child: const Icon(Icons.auto_awesome, color: Colors.white),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('AI Chat', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              Text('Research OS Copilot • ${widget.teamName} • $_status',
                  maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant)),
            ],
          ),
        ),
        IconButton(tooltip: 'ประวัติแชต', onPressed: _showHistory, icon: const Icon(Icons.history)),
        IconButton(tooltip: 'แชตใหม่', onPressed: _newChat, icon: const Icon(Icons.add_comment_outlined)),
        PopupMenuButton<String>(
          tooltip: 'ตัวเลือกแชต',
          onSelected: (value) {
            if (value == 'clear') setState(_messages.clear);
            if (value == 'context') _addContext();
          },
          itemBuilder: (context) => const [
            PopupMenuItem(value: 'context', child: ListTile(dense: true, leading: Icon(Icons.attach_file), title: Text('เพิ่มบริบท'))),
            PopupMenuItem(value: 'clear', child: ListTile(dense: true, leading: Icon(Icons.delete_outline), title: Text('ล้างหน้าต่างแชต'))),
          ],
        ),
      ],
    );
  }

  Widget _welcome(ThemeData theme) {
    final colors = theme.colorScheme;
    final suggestions = <({IconData icon, String title, String prompt})>[
      (icon: Icons.travel_explore, title: 'ค้นคว้าข้อมูล', prompt: 'ช่วยค้นคว้าและสรุปหัวข้อนี้ พร้อมแยกข้อเท็จจริงกับข้อสันนิษฐาน: '),
      (icon: Icons.analytics_outlined, title: 'วิเคราะห์ปัญหา', prompt: 'ช่วยวิเคราะห์ปัญหานี้ หาสาเหตุราก และเสนอวิธีตรวจสอบ: '),
      (icon: Icons.account_tree_outlined, title: 'วางแผนโครงการ', prompt: 'ช่วยจัดทำแผนโครงการ แบ่งขั้นตอน งานย่อย และเกณฑ์ผ่าน: '),
      (icon: Icons.fact_check_outlined, title: 'ตรวจสอบคุณภาพ', prompt: 'ช่วยตรวจสอบความถูกต้อง ความเสี่ยง และหลักฐานที่ต้องใช้: '),
    ];
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            children: [
              Container(
                width: 68, height: 68,
                decoration: BoxDecoration(color: colors.primary.withValues(alpha: .10), borderRadius: BorderRadius.circular(22)),
                child: Icon(Icons.auto_awesome, size: 34, color: colors.primary),
              ),
              const SizedBox(height: 18),
              Text('สวัสดีครับ พร้อมเริ่มงานวิจัยหรือยัง?',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              Text('ถามคำถาม วิเคราะห์ข้อมูล วางแผนงาน หรือให้ Research OS ช่วยตรวจสอบงานของคุณ',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(color: colors.onSurfaceVariant)),
              const SizedBox(height: 24),
              Wrap(
                spacing: 10, runSpacing: 10, alignment: WrapAlignment.center,
                children: suggestions.map((item) => SizedBox(
                  width: 285,
                  child: OutlinedButton(
                    key: Key('ai-prompt-${item.title}'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.all(15),
                      alignment: Alignment.centerLeft,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                    onPressed: () {
                      _input.text = item.prompt;
                      _input.selection = TextSelection.collapsed(offset: _input.text.length);
                    },
                    child: Row(children: [
                      Icon(item.icon, size: 20),
                      const SizedBox(width: 10),
                      Expanded(child: Text(item.title)),
                      const Icon(Icons.arrow_outward, size: 16),
                    ]),
                  ),
                )).toList(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _conversation(ThemeData theme) {
    return ListView.builder(
      key: const Key('ai-chat-messages'),
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(22, 24, 22, 28),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        final message = _messages[index];
        final user = message.role == 'user';
        final colors = theme.colorScheme;
        return Align(
          alignment: user ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 820),
            margin: const EdgeInsets.only(bottom: 16),
            padding: const EdgeInsets.all(15),
            decoration: BoxDecoration(
              color: message.isError
                  ? colors.errorContainer.withValues(alpha: .65)
                  : user ? colors.primary.withValues(alpha: .10) : colors.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: colors.outline.withValues(alpha: .10)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(user ? Icons.person_outline : Icons.auto_awesome, size: 17,
                      color: user ? colors.primary : colors.tertiary),
                  const SizedBox(width: 7),
                  Text(user ? 'คุณ' : 'Research OS AI',
                      style: theme.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const Spacer(),
                  Text(_time(message.createdAt), style: theme.textTheme.labelSmall?.copyWith(color: colors.onSurfaceVariant)),
                  if (!user) IconButton(
                    tooltip: 'คัดลอกคำตอบ',
                    visualDensity: VisualDensity.compact,
                    onPressed: () => _copy(message.text),
                    icon: const Icon(Icons.copy_outlined, size: 16),
                  ),
                ]),
                const SizedBox(height: 8),
                SelectableText(message.text, style: theme.textTheme.bodyLarge),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _composer(ThemeData theme) {
    final colors = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            DropdownButton<_ChatMode>(
              key: const Key('ai-chat-mode'),
              value: _mode,
              underline: const SizedBox.shrink(),
              borderRadius: BorderRadius.circular(12),
              items: _ChatMode.values.map((mode) => DropdownMenuItem(
                value: mode,
                child: Text(mode.label),
              )).toList(),
              onChanged: _busy ? null : (value) { if (value != null) setState(() => _mode = value); },
            ),
            const SizedBox(width: 8),
            FilterChip(
              key: const Key('ai-chat-turbo'),
              selected: _turbo,
              onSelected: _busy ? null : (value) => setState(() => _turbo = value),
              avatar: const Icon(Icons.bolt, size: 16),
              label: const Text('Turbo'),
            ),
            const Spacer(),
            if (_context.isNotEmpty)
              Chip(
                avatar: const Icon(Icons.attach_file, size: 15),
                label: const Text('มีบริบทแนบแล้ว'),
                onDeleted: () => setState(() => _context = ''),
              ),
            IconButton(
              tooltip: 'เพิ่มบริบท/ข้อความอ้างอิง',
              onPressed: _busy ? null : _addContext,
              icon: const Icon(Icons.add_link),
            ),
          ]),
          Container(
            decoration: BoxDecoration(
              color: colors.surfaceContainerLow,
              borderRadius: BorderRadius.circular(17),
              border: Border.all(color: colors.outline.withValues(alpha: .16)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('ai-chat-input'),
                    controller: _input,
                    minLines: 1,
                    maxLines: 5,
                    enabled: !_busy,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(
                      hintText: 'ส่งข้อความถึง Research OS AI...',
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.fromLTRB(17, 14, 8, 14),
                      suffixIcon: _input.text.isEmpty ? null : IconButton(
                        tooltip: 'ล้างข้อความ',
                        onPressed: () => setState(_input.clear),
                        icon: const Icon(Icons.close, size: 18),
                      ),
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(right: 7, bottom: 7),
                  child: IconButton.filled(
                    key: const Key('ai-chat-send'),
                    tooltip: 'ส่งข้อความ',
                    onPressed: _busy ? null : _send,
                    icon: _busy
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.arrow_upward),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          Text(_mode.description, style: theme.textTheme.labelSmall?.copyWith(color: colors.onSurfaceVariant)),
        ],
      ),
    );
  }

  Widget _metrics(ThemeData theme) {
    final values = <String>[
      'Brain: $_brainScale',
      'Capacity: $_capacity',
      'Workers: $_workers',
      'Batches: $_batches',
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(children: values.map((value) => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(9),
          ),
          child: Text(value, style: theme.textTheme.labelSmall),
        ),
      )).toList()),
    );
  }

  String _time(DateTime value) =>
      '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
}

class _ContextDialog extends StatefulWidget {
  const _ContextDialog({required this.initialText});

  final String initialText;

  @override
  State<_ContextDialog> createState() => _ContextDialogState();
}

class _ContextDialogState extends State<_ContextDialog> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialText);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('เพิ่มบริบทให้ AI'),
      content: SizedBox(
        width: 520,
        child: TextField(
          controller: _controller,
          minLines: 4,
          maxLines: 9,
          decoration: const InputDecoration(
            hintText: 'วางข้อความหรือรายละเอียดที่ต้องการให้ AI ใช้ประกอบคำตอบ',
            border: OutlineInputBorder(),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('ยกเลิก'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _controller.text.trim()),
          child: const Text('ใช้บริบทนี้'),
        ),
      ],
    );
  }
}

class _ChatTurn {
  const _ChatTurn({
    required this.role,
    required this.text,
    required this.createdAt,
    this.isError = false,
  });

  final String role;
  final String text;
  final DateTime createdAt;
  final bool isError;
}

class _ChatSession {
  const _ChatSession({
    required this.title,
    required this.messages,
    required this.createdAt,
  });

  final String title;
  final List<_ChatTurn> messages;
  final DateTime createdAt;
}
