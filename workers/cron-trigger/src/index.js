export default {
  async scheduled(event, env) {
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

    console.log("Dispatched daily-refresh workflow");
  },
};
