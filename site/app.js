const el = (id) => document.getElementById(id);

function formatBytes(bytes) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(bytes / 1_000_000_000) + " GB";
}

function validRelease(release) {
  return (
    ["available", "preview"].includes(release.status) &&
    typeof release.version === "string" &&
    typeof release.downloadUrl === "string" &&
    release.downloadUrl.startsWith("https://github.com/") &&
    typeof release.filename === "string" &&
    Number.isSafeInteger(release.size) &&
    /^[a-f0-9]{64}$/.test(release.sha256) &&
    release.localOnlySmokePassed === true
  );
}

function enableDownload(release) {
  const buttons = [el("hero-download"), el("download-button")];
  buttons.forEach((button) => {
    button.href = release.downloadUrl;
    button.classList.remove("disabled");
    button.removeAttribute("aria-disabled");
    button.textContent = "Download Field Kit Lite";
  });

  const details = `${release.version} · Windows 10/11 x64 · ${formatBytes(release.size)}`;
  el("hero-meta").textContent = `${details} · Complete offline installer`;
  el("download-title").textContent = "Install once. Work offline.";
  el("download-copy").textContent = "One verified download contains the application, CPU runtime, Lite model, starter knowledge, and third-party licenses.";
  el("download-meta").textContent = `${details} · 8 GB RAM · 6 GB free disk`;
  el("checksum").textContent = release.sha256;
  el("available-details").classList.remove("hidden");
  el("release-notes").href = release.releaseUrl;

  const signature = el("signature-note");
  if (release.signed === true) {
    signature.textContent = `Windows publisher: ${release.publisher}. If the publisher does not match, stop.`;
  } else {
    signature.textContent = "Unsigned preview: Windows SmartScreen or an organization policy may block this build. Do not bypass a block on a customer system; use the source build or wait for a signed release.";
  }
}

function showPreparing(release = {}) {
  const progressUrl = release.progressUrl || "https://github.com/ben4mn/field-tech-copilot/issues/3";
  el("hero-meta").innerHTML = `The one-click bundle is being verified. <a href="${progressUrl}">Follow packaging progress.</a>`;
  el("download-copy").textContent = "The application is working, but the downloadable bundle has not passed its release checks yet.";
}

async function loadRelease() {
  try {
    const response = await fetch(`release.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error("release manifest unavailable");
    const release = await response.json();
    if (validRelease(release)) enableDownload(release);
    else showPreparing(release);
  } catch {
    showPreparing();
  }
}

el("copy-checksum").addEventListener("click", async () => {
  await navigator.clipboard.writeText(el("checksum").textContent);
  el("copy-checksum").textContent = "Copied";
  window.setTimeout(() => { el("copy-checksum").textContent = "Copy"; }, 1800);
});

const dialog = el("preview-dialog");
el("open-preview").addEventListener("click", () => dialog.showModal());
el("close-preview").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

loadRelease();
