# Offline YAML dependency

`yaml.js` bundles [yaml 2.9.1](https://github.com/eemeli/yaml) under its ISC
license (see `LICENSE.txt`). It is served locally; the editor makes no requests
to a package registry or CDN.

To rebuild from the repository root with Node.js installed:

```sh
npm install --prefix .cache/config-editor-vendor --no-package-lock --ignore-scripts --no-audit --no-fund yaml@2.9.1 esbuild@0.28.2
node -e "require('./.cache/config-editor-vendor/node_modules/esbuild').buildSync({entryPoints:['./config-editor/vendor/yaml-entry.js'],nodePaths:['.cache/config-editor-vendor/node_modules'],tsconfigRaw:{},bundle:true,format:'iife',globalName:'YAML',minify:true,legalComments:'inline',outfile:'config-editor/vendor/yaml.js'})"
```

Retain `LICENSE.txt` when distributing this bundle. Node.js is only needed to
rebuild the dependency, not to use the editor.
