# Sekai Core Protocol v0.1

All communication is done via JSON over STDIN/STDOUT.

Each request MUST include:
- cmd: string
- id: any (optional, echoed back)

Each response includes:
- id
- status: "ok" | "error"
- payload (on success)
- message (on error)

---

## Commands

### ping
Payload: none  
Response:
{ message: string }

### parse_text
Payload:
{ text: string }

Response:
{ entries: CoreEntry[] }

### rebuild_text
Payload:
{ entries: CoreEntry[] }

Response:
{ text: string }

### detect_encoding
Payload:
{ path: string }

Response:
{
  best: string,
  confidence: number,
  candidates: [...]
}

...
