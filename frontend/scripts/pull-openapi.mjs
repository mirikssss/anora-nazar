// Забирает OpenAPI работающих сервисов в openapi/: адреса — из окружения, как у прокси.
import { writeFile } from "node:fs/promises";

const sources = { node: "WEB_NODE_UPSTREAM", "bank-sim": "WEB_BANK_UPSTREAM" };

for (const [name, variable] of Object.entries(sources)) {
  const base = process.env[variable];
  if (!base) throw new Error(`Не задана переменная окружения ${variable}`);
  const response = await fetch(`${base}/openapi.json`);
  if (!response.ok) throw new Error(`${name}: ${response.status} ${response.statusText}`);
  await writeFile(`openapi/${name}.json`, JSON.stringify(await response.json(), null, 2) + "\n");
  console.log(`openapi/${name}.json обновлён`);
}
