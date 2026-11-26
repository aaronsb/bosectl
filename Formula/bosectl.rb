class Bosectl < Formula
  include Language::Python::Virtualenv

  desc "Control Bose headphones over Bluetooth RFCOMM using the BMAP protocol"
  homepage "https://github.com/aaronsb/bosectl"
  url "https://github.com/aaronsb/bosectl/archive/refs/tags/v0.6.0.tar.gz"
  sha256 "9f5e2d6e4ffed94f2a53b9053af9afac6e382a6d882f07cddb4090beb1742143"
  license "MIT"
  head "https://github.com/aaronsb/bosectl.git", branch: "main"

  depends_on "rust" => :build
  depends_on :macos
  depends_on "python@3.12"

  resource "pyobjc-core" do
    url "https://files.pythonhosted.org/packages/36/5f/b14b6b66a38f628af7a0983728f8d7360f17b68075bcd86631872aa7bb71/pyobjc_core-13.1.tar.gz"
    sha256 "fd73c9020389c325d2045992134a8d89f8f554b46084c8ff36fe05a54bc9996e"
  end

  resource "pyobjc-framework-Cocoa" do
    url "https://files.pythonhosted.org/packages/8d/f9/20f550e334092a7e762fc9a9e8214ea4750b622c08b594c20782910daa31/pyobjc_framework_cocoa-13.1.tar.gz"
    sha256 "2f373dedbfffc236ed2f6278b45ea5f053940e621a486b2e9f4d23a06b06ba22"
  end

  resource "pyobjc-framework-IOBluetooth" do
    url "https://files.pythonhosted.org/packages/83/ce/e0ccbdbe0bcf491dd984db733b7e20dc0f62b474ed1bcca7f09292352926/pyobjc_framework_iobluetooth-13.1.tar.gz"
    sha256 "4321b495de2934ac30653f806a616c92ed5f67dcfc929b916ac5c140752d232c"
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install resources
    venv.pip_install_and_link buildpath/"python"

    system "cargo", "install", *std_cargo_args(path: "rust"), "--bin", "bmapctl"

    zsh_completion.install "completion/_bosectl"
    bash_completion.install "completion/bosectl.bash" => "bosectl"
  end

  service do
    run [opt_bin/"bosectl", "status"]
    run_type :interval
    interval 300
    log_path var/"log/bosectl.log"
    error_log_path var/"log/bosectl.log"
  end

  test do
    assert_match "bosectl", shell_output("#{bin}/bosectl --help 2>&1", 1)
    assert_match "bmapctl", shell_output("#{bin}/bmapctl --help")
  end
end
