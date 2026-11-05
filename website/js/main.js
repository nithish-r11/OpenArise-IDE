/**
 * OpenArise IDE – Official Download Page Scripts
 * Handles configurable download links, copy-to-clipboard, and navigation tracking.
 */

// Centralized Configurable Download URLs
// When publishing to GitHub Releases, update isPublished to true and set real URLs.
const DOWNLOAD_CONFIG = {
  isPublished: true,
  version: "1.0.0",
  installerUrl: "https://github.com/nithish-r11/OpenArise-IDE/releases/download/v1.0.0/OpenAriseIDE-Setup-1.0.0.exe",
  portableUrl: "https://github.com/nithish-r11/OpenArise-IDE/releases/download/v1.0.0/OpenAriseIDE.exe",
  releaseNotesUrl: "#release-notes"
};

document.addEventListener("DOMContentLoaded", () => {
  setupDownloadButtons();
  setupCopyButtons();
  setupNavigationTracking();
});

/**
 * Configure download buttons based on publication state.
 */
function setupDownloadButtons() {
  const installerBtn = document.getElementById("downloadInstallerBtn");
  const portableBtn = document.getElementById("downloadPortableBtn");
  const banner = document.getElementById("statusBanner");

  function handleDownloadClick(e, type) {
    e.preventDefault();
    if (DOWNLOAD_CONFIG.isPublished) {
      const url = type === "installer" ? DOWNLOAD_CONFIG.installerUrl : DOWNLOAD_CONFIG.portableUrl;
      window.location.href = url;
    } else {
      // Show clear coming soon notification
      if (banner) {
        banner.style.transition = "transform 0.2s ease, box-shadow 0.2s ease";
        banner.style.transform = "scale(1.02)";
        banner.style.boxShadow = "0 0 0 3px rgba(245, 158, 11, 0.4)";
        setTimeout(() => {
          banner.style.transform = "scale(1)";
          banner.style.boxShadow = "none";
        }, 600);
      }
      alert(
        "Coming Soon – Public Download Not Yet Available\n\n" +
        "OpenArise IDE v" + DOWNLOAD_CONFIG.version + " has been compiled and verified locally. " +
        "Public downloads will be accessible here as soon as the GitHub Release is published."
      );
    }
  }

  if (installerBtn) {
    installerBtn.addEventListener("click", (e) => handleDownloadClick(e, "installer"));
  }
  if (portableBtn) {
    portableBtn.addEventListener("click", (e) => handleDownloadClick(e, "portable"));
  }
}

/**
 * One-click copy for code blocks and SHA-256 hashes.
 */
function setupCopyButtons() {
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const textToCopy = btn.getAttribute("data-copy");
      if (!textToCopy) return;

      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = btn.textContent;
        btn.textContent = "Copied!";
        btn.classList.add("copied");

        setTimeout(() => {
          btn.textContent = originalText;
          btn.classList.remove("copied");
        }, 2000);
      } catch (err) {
        // Fallback for non-https or older browsers
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        try {
          document.execCommand("copy");
          const originalText = btn.textContent;
          btn.textContent = "Copied!";
          btn.classList.add("copied");
          setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove("copied");
          }, 2000);
        } catch (e) {
          console.error("Failed to copy:", e);
        }
        document.body.removeChild(textarea);
      }
    });
  });
}

/**
 * Update active navigation links when scrolling through sections.
 */
function setupNavigationTracking() {
  const sections = document.querySelectorAll("section[id]");
  const navLinks = document.querySelectorAll(".nav-link");

  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute("id");
          navLinks.forEach((link) => {
            const href = link.getAttribute("href");
            if (href === `#${id}`) {
              link.classList.add("active");
            } else {
              link.classList.remove("active");
            }
          });
        }
      });
    },
    {
      rootMargin: "-20% 0px -70% 0px"
    }
  );

  sections.forEach((sec) => observer.observe(sec));
}

