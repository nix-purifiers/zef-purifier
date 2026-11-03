{
  symlinkJoin,
  nativeZef,
  rakudo,
  git,
  curl,
  gnutar,
  gzip,
  unzip,
  gnumake,
  gcc,
  cacert,
}:
symlinkJoin {
  name = "zef-purifier-toolchain";
  paths = [
    nativeZef
    rakudo
    git
    curl
    gnutar
    gzip
    unzip
    gnumake
    gcc
    cacert
  ];
}
