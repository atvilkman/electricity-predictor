const fs = require("fs");
const path = require("path");

function copyFile(name) {
  const src = path.join(__dirname, "..", "..", "data", name);
  const destDir = path.join(__dirname, "..", "public", "data");
  fs.mkdirSync(destDir, { recursive: true });
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(destDir, name));
    console.log(`Copied ${name} to public/data/`);
  } else {
    console.log(`Skipped ${name} (not found yet)`);
  }
}

copyFile("web_snapshot.json");
copyFile("grid_snapshot.json");
copyFile("hourly_snapshot.json");
