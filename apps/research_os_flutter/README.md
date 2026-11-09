# Research OS Flutter

แอป Flutter แบบข้ามแพลตฟอร์มสำหรับใช้เป็นหน้าบ้านของ Research OS โดยไม่ฝัง Gemini API key หรือ GitHub token ไว้ใน client

## สถานะ Sprint 1

- Material 3 application shell
- Home dashboard
- Research OS API health/provider client
- AI Memory client methods
- Widget test
- GitHub Actions สำหรับ analyze, test และ build web

## รันในเครื่อง

เปิด Research OS API ก่อนจากราก repository:

```bash
python tools/research_os_api/server.py --host 127.0.0.1 --port 0
```

API และ Developer API จะขอ Port `0` เพื่อให้ OS จัดสรร Port จริง แล้วเขียน endpoint ลง `%ProgramData%\\ResearchOS\\runtime\\api.json` และ `developer.json` (Friend ใช้ `friend.json`). Windows Flutter อ่าน endpoint ปัจจุบันจาก registry โดยอัตโนมัติ ไม่ต้องล็อกหรือกรอก Port.

จากนั้น:

```bash
cd apps/research_os_flutter
flutter create --platforms=web,android,ios,windows,macos,linux .
flutter pub get
flutter run
```

สำหรับ Android emulator หรืออุปกรณ์ที่อ่าน Windows runtime registry ไม่ได้ ให้ใช้ Port จริงจาก `api.json` ใน URL `http://10.0.2.2:<GENERATED_API_PORT>` (Android emulator) หรือกำหนด HTTPS endpoint สำหรับ Cloud/Tailscale ผ่าน `RESEARCH_OS_API_BASE_URL`.

## Security

- Gemini API key อยู่ฝั่ง Research OS API เท่านั้น
- แอป Flutter เรียก backend ผ่าน HTTP API
- Local API, Friend และ Developer API bind เฉพาะ loopback
- ก่อนเปิดใช้งานผ่านเครือข่ายจริง ต้องใช้ Authentication, TLS, CORS policy และ rate limiting ที่ backend
