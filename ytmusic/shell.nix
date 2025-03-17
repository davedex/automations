let
  pkgs = import <nixpkgs> {};
  python = pkgs.python312;
  pythonPackages = python.pkgs;
  lib-path = with pkgs; lib.makeLibraryPath [
    libffi
    openssl
    stdenv.cc.cc
  ];
in with pkgs; mkShell {
  packages = [
    pythonPackages.discordpy
    pythonPackages.beautifulsoup4
    pythonPackages.lxml

    pkgs.chromedriver
    pkgs.chromium

    # Create a script to run chromium
    (pkgs.writeShellScriptBin "chromium" "exec -a $0 ${pkgs.chromium}/bin/chromium $@")
  ];

  buildInputs = [
    readline
    libffi
    openssl
    git
    openssh
    rsync
  ];

  shellHook = ''
    SOURCE_DATE_EPOCH=$(date +%s)
    export "LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${lib-path}"
    VENV=.venv

    if test ! -d $VENV; then
      python3.12 -m venv $VENV
    fi
    source ./$VENV/bin/activate
    export PYTHONPATH=`pwd`/$VENV/${python.sitePackages}/:$PYTHONPATH
    pip install -r requirements.txt
  '';

  postShellHook = ''
    ln -sf ${python.sitePackages}/* ./.venv/lib/python3.12/site-packages
  '';
}
