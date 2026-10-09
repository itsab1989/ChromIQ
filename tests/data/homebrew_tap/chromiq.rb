cask "chromiq" do
  arch arm: "arm64", intel: "x86_64"

  version "4.3.2"
  sha256 arm:   "eacd1a639faafa014531b8911b8d0c15a186774bfe8b7976cd56f905177cc4d7",
         intel: "d80c832ee86f8bd0ef5cfdf2d7e82aee21d1c209d8570aba2564ab5a179a63ad"

  url "https://github.com/itsab1989/ChromIQ/releases/download/v#{version}/ChromIQ-macOS-#{arch}_v#{version}.dmg",
      verified: "github.com/itsab1989/ChromIQ/"
  name "ChromIQ"
  desc "GUI for ICC printer profiling with ArgyllCMS"
  homepage "https://github.com/itsab1989/ChromIQ"

  livecheck do
    url :url
    strategy :github_latest
  end

  conflicts_with cask: "chromiq@beta"
  depends_on formula: "argyll-cms"
  depends_on macos: :ventura

  app "ChromIQ.app"

  # ChromIQ is ad-hoc signed, not notarised by Apple. Without this step
  # macOS would refuse to open it on first launch ("Apple could not verify
  # ..."), so the cask removes the download quarantine from the installed app.
  postflight_steps do
    run "/usr/bin/xattr",
        args:           ["-dr", "com.apple.quarantine", "{{appdir}}/ChromIQ.app"],
        writable_paths: ["ChromIQ.app"],
        writable_base:  :appdir
  end

  # Never ~/ChromIQ: those are the user's own projects.
  zap trash: [
    "~/Library/Caches/ChromIQ",
    "~/Library/Logs/ChromIQ",
    "~/Library/Preferences/com.chromiq.ChromIQ.plist",
    "~/Library/Saved Application State/com.chromiq.app.savedState",
  ]
end
