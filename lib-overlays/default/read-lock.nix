{ lib }:
{
  src,
  lockFile ? src + "/zef-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  distributions = data.distributions or [ ];
  inputs = data.inputs or { };
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "zef"
    && builtins.isAttrs inputs
    && builtins.attrNames inputs == [ "META6.json" ]
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs inputs.${name}
      && builtins.isString (inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" inputs.${name}.content == inputs.${name}.sha256
    ) (builtins.attrNames inputs)
    && builtins.isList entries
    && builtins.isList distributions
    && builtins.length entries == builtins.length distributions
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.match "archives/[0-9]{4}\\.tar\\.gz" e.path != null
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.all (
      d:
      builtins.isAttrs d
      && builtins.isString (d.identity or null)
      && builtins.isString (d.request or null)
      && builtins.isAttrs (d.meta or null)
      && builtins.isAttrs (d.meta.provides or null)
      && builtins.all relative (builtins.attrValues d.meta.provides)
      && builtins.any (e: e.path == (d.path or null)) entries
    ) distributions
    && builtins.length (lib.unique (map (d: d.identity) distributions)) == builtins.length distributions
    && builtins.isAttrs (data.toolVersions or null)
    && builtins.all (k: builtins.isString (data.toolVersions.${k} or null)) [
      "sdk"
      "rakudo"
      "zef"
      "gcc"
    ];
in
{
  purifier = "zef";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Zef lock is missing, stale, or unsupported; run zef-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
