# Upstream compatibility patches

`vcmi-1.6.5-sdl-mixer.patch` replaces a hard-coded `Mix_Music` forward-declaration
alias with the SDL_mixer header's authoritative declaration. Debian 13's
SDL_mixer 2.8.1 headers use a different underlying struct name than VCMI 1.6.5
expects. The patch is applied to the local source tree used for this build.
It changes compilation compatibility, not game behavior or adapter decisions.

For a fresh VCMI 1.6.5 checkout, apply from the checkout root:

```bash
git apply /absolute/path/to/H3_BOT/patches/vcmi-1.6.5-sdl-mixer.patch
```
