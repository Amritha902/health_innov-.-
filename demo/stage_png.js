// Renders the static stage graphics for phone scenes (background with headline, and the phone frame).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const OUT = path.join(process.argv[2], "stage");
fs.mkdirSync(OUT, { recursive: true });
const script = JSON.parse(fs.readFileSync(path.join(__dirname, "script.json")));
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const sc of script.filter(s => s.kind === "phone")) {
    await p.goto(`http://localhost:8000/_stage.html?mode=stage&head=${encodeURIComponent(sc.head)}&sub=${encodeURIComponent(sc.sub)}`);
    await p.waitForTimeout(400);
    await p.screenshot({ path: path.join(OUT, sc.id + ".png") });
  }
  await p.goto("http://localhost:8000/_stage.html?mode=frame"); await p.waitForTimeout(200);
  await p.screenshot({ path: path.join(OUT, "frame.png"), omitBackground: true });
  await b.close();
})();
