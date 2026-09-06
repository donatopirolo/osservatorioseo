// Sveglia il workflow daily-refresh alle 07:00 ora di Roma.
//
// I due cron in wrangler.toml (05:00 e 06:00 UTC) coprono ora legale e ora
// solare: solo uno dei due corrisponde alle 07:00 a Roma, e questo controllo
// scarta l'altro. Senza, la pipeline gira due volte al giorno.

const TARGET_HOUR_ROME = 7;

function hourInRome(date) {
  const formatted = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome",
    hour: "2-digit",
    hourCycle: "h23",
  }).format(date);
  return Number.parseInt(formatted, 10);
}

export default {
  async scheduled(event, env) {
    const now = new Date(event.scheduledTime ?? Date.now());
    const hour = hourInRome(now);

    if (hour !== TARGET_HOUR_ROME) {
      console.log(
        `Skip: a Roma sono le ${hour}, non le ${TARGET_HOUR_ROME}. ` +
          `Il cron dell'altro fuso ha gia' fatto (o fara') il dispatch.`
      );
      return;
    }

    const res = await fetch(
      "https://api.github.com/repos/donatopirolo/osservatorioseo/actions/workflows/daily-refresh.yml/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "osservatorioseo-cron-worker",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`GitHub API ${res.status}: ${body}`);
    }

    console.log(`Dispatched daily-refresh workflow (ore ${hour} a Roma)`);
  },
};
