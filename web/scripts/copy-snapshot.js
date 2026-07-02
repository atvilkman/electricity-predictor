const fs = require("fs");
const path = require("path");
const src = path.join(__dirname, "..", "..", "data", "web_snapshot.json");
const destDir = path.join(__dirname, "..", "public", "data");
fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, path.join(destDir, "web_snapshot.json"));
console.log("Copied web_snapshot.json to public/data/");
