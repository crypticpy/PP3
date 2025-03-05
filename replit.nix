{pkgs}: {
  deps = [
    pkgs.bash
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.pkg
    pkgs.libxcrypt
  ];
}
