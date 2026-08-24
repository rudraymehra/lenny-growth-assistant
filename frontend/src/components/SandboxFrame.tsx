// The client half of artifact isolation (server half: artifacts/sanitizer.py).
//
// sandbox="" (empty allowlist) means the document gets NO scripts, NO
// same-origin access (it is an opaque origin — no cookies, no storage, no
// parent DOM), NO forms, NO popups, NO top-navigation. The injected CSP is
// belt-and-braces: even if markup slipped past the server sanitizer, the
// document may load nothing but inline styles and https images.

// img-src https: (no data:) matches the server sanitizer, which allows only
// https images and strips CSS url()/@import. No script-src, connect-src, or
// frame-src: the document can style itself and show https images — nothing
// else can execute or phone home.
const CSP =
  "default-src 'none'; style-src 'unsafe-inline'; img-src https:; font-src 'none'";

export default function SandboxFrame({ html, title }: { html: string; title: string }) {
  const doc = `<!doctype html><html><head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>body{font-family:system-ui,-apple-system,sans-serif;margin:16px;line-height:1.55}</style>
</head><body>${html}</body></html>`;

  return (
    <iframe
      title={`Artifact preview: ${title}`}
      sandbox=""
      srcDoc={doc}
      className="h-full w-full border-0 bg-white"
    />
  );
}
