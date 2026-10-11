// Что банк знает до заявки: самозапрет в реестре и события сессии в приложении.
import { bankApi, request, type BankSchemas } from "@/shared/api";

export type SelfBanStatus = BankSchemas["schemas"]["SelfBanIn"]["status"];
export type SessionEventType = BankSchemas["schemas"]["SessionEventIn"]["event_type"];

export async function setSelfBan(pinfl: string, status: SelfBanStatus): Promise<void> {
  await request(bankApi.PUT("/v1/sources/self-bans", { body: { pinfl, status } }));
}

export async function recordSessionEvent(
  pinfl: string,
  eventType: SessionEventType,
  deviceId: string | null,
): Promise<string> {
  const event = await request(
    bankApi.POST("/v1/sessions/events", { body: { pinfl, event_type: eventType, device_id: deviceId } }),
  );
  return event.session_event_id;
}
