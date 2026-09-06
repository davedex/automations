# NixOS configuration module for YouTube Music Header Refresh Service and Timer.
# You can import this file directly in your NixOS /etc/nixos/configuration.nix using:
#   imports = [ ./refresh_ytmusic_headers.nix ];
#
# Make sure to rebuild your NixOS system afterward:
#   sudo nixos-rebuild switch

{ config, pkgs, ... }:

{
  systemd.services.refresh-ytmusic-headers = {
    description = "Refresh YouTube Music Authentication Headers";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];

    serviceConfig = {
      Type = "oneshot";
      User = "ddexter";
      WorkingDirectory = "/home/ddexter/automations/ytmusic";

      # Runs the refresh script inside the Nix Flake dev environment of the workspace
      # to ensure chromium and chromedriver are automatically available.
      ExecStart = "${pkgs.nix}/bin/nix develop /home/ddexter/automations/ytmusic --command /home/ddexter/automations/ytmusic/.venv/bin/python /home/ddexter/automations/ytmusic/refresh_headers.py";

      Environment = [
        "HOME=/home/ddexter"
        "PATH=/run/current-system/sw/bin"
        "SOPS_AGE_KEY_FILE=/home/ddexter/.config/sops/age/keys.txt"
      ];

      TimeoutSec = 120;
    };
  };

  systemd.timers.refresh-ytmusic-headers = {
    description = "Run YouTube Music header refresh daily at random times";
    wantedBy = [ "timers.target" ];

    timerConfig = {
      OnCalendar = "daily";
      # 6 hours of randomized delay to avoid detection
      RandomizedDelaySec = "21600";
      Persistent = true;
    };
  };
}
