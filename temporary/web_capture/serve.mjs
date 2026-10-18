// 预览用静态服务：显式声明 charset 并禁用缓存，避免浏览器按本地编码解 UTF-8。
import { createServer } from "node:http";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")));
const PORT = Number(process.argv[2] ?? 8100);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
};

createServer((req, res) => {
  const requested = decodeURIComponent((req.url ?? "/").split("?")[0]);
  const file = path.join(ROOT, requested === "/" ? "ui.html" : requested);
  if (!file.startsWith(ROOT)) {
    res.writeHead(403, { "content-type": "text/plain; charset=utf-8" }).end("403");
    return;
  }
  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404, { "content-type": "text/plain; charset=utf-8" }).end("404 " + requested);
      return;
    }
    res
      .writeHead(200, {
        "content-type": TYPES[path.extname(file).toLowerCase()] ?? "application/octet-stream",
        "cache-control": "no-store, must-revalidate",
      })
      .end(data);
  });
}).listen(PORT, "127.0.0.1", () => {
  console.log(`preview: http://127.0.0.1:${PORT}/ui.html`);
});
