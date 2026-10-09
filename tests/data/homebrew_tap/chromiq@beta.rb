cask "chromiq@beta" do
  arch arm: "arm64", intel: "x86_64"

  version "4.3.3-beta.16"
  sha256 arm:   "d6dbd5109885381d255b2dceeaa7f01173b9bc6fd07e1a1067d0dfa175908844",
         intel: "1d21f283f1db9fb908dae193e604e6aea81933abd030a5903d3eef0d180767e5"

  url "https://github.com/itsab1989/ChromIQ/releases/download/v#{version}/ChromIQ-macOS-#{arch}_v#{version}.dmg",
      verified: "github.com/itsab1989/ChromIQ/"
  name "ChromIQ (beta)"
  desc "GUI for ICC printer profiling with ArgyllCMS"
  homepage "https://github.com/itsab1989/ChromIQ"

  # The newest release, beta or stable: the GitHub API lists pre-releases too.
  livecheck do
    url "https://api.github.com/repos/itsab1989/ChromIQ/releases"
    strategy :json do |json|
      json.filter_map do |release|
        next if release["draft"]

        release["tag_name"]&.delete_prefix("v")
      end
    end
  end

  conflicts_with cask: "chromiq"
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
