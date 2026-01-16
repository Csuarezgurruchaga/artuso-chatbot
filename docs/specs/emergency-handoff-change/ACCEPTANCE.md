# Acceptance Criteria

## Functional
1. **Emergency detection sources**
   - Menu button “emergencia”, keyword matches, and NLU classification all trigger the emergency flow.
   - Works for both WhatsApp and Messenger.

2. **Emergency message content**
   - The client receives exactly:
     "🚨 *Emergencia detectada*\n\nPara una atención inmediata, comunicate directamente con nuestro equipo al siguiente número:\n\n📞 *11-5609-6511*\n\nEste canal es el más rápido para resolver situaciones urgentes.\nEl chatbot no gestiona emergencias en tiempo real."
   - The number is sourced from `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` and displayed as `11-XXXX-XXXX`.

3. **No handoff for emergencies**
   - No handoff queue entry is created for emergencies.
   - No template or agent notification is sent for emergencies.

4. **Missing/invalid emergency number**
   - When `HANDOFF_EMERGENCY_WHATSAPP_NUMBER` is missing/invalid, an ERROR log is emitted that clearly names the env var.
   - The emergency message is not sent.

5. **Post-message behavior**
   - If emergency is detected outside a mid-flow state, the conversation is finalized.
   - The next user input (text or media) starts a new flow without requiring “hola”.

6. **Mid-flow pause/resume**
   - If emergency is detected mid-flow, the flow is paused and data preserved.
   - Only `CONTINUAR` resumes the previous step.
   - Any other input does not resume the flow (emergency message may be re-sent).

7. **Emergency during handoff**
   - If a conversation is already in handoff/queue, the queue state remains unchanged.
   - The emergency message is sent to the client and no agent notification is added.

8. **Rate limit**
   - Emergency flow does not bypass daily rate limit checks.

## Non-functional
- No new dependencies added.
- No measurable latency increase in normal (non-emergency) flows.

## Observability
- INFO logs for emergency detection and send status.
- ERROR logs for missing/invalid emergency number.
