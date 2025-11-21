# Workflow README

This is a placeholder export. Wire your Dify/n8n HTTP node to POST `/predict`:
- URL: `https://<YOUR-DOMAIN>/predict`
- Body: `{ "query": "{{input.text}}", "user_id": "{{user.id}}", "tool_name": "dosm_faq" }`

Map response fields into your chat UI:
- `prediction.answer`
- `prediction.citations[*]`
