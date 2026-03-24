# Neovim lazy.nvim Migration Design

**Date:** 2026-03-23

**Goal:** Move the user's Neovim plugin management to `lazy.nvim` while keeping the existing `init.vim`-based editor settings intact and adding `markdown-preview.nvim`.

## Current State

- Neovim version: `v0.11.6`
- Config file: `~/.config/nvim/init.vim`
- Current plugin install method: native `pack/*/start`
- Current managed plugins:
  - `nvim-treesitter/nvim-treesitter`
  - `olimorris/onedarkpro.nvim`

## Design

- Keep `init.vim` as the main entry point for existing Vimscript options.
- Remove plugin-specific setup from `init.vim`.
- Bootstrap `lazy.nvim` from `init.vim`.
- Store plugin specs in `lua/plugins.lua`.
- Manage these plugins with `lazy.nvim`:
  - `nvim-treesitter/nvim-treesitter`
  - `olimorris/onedarkpro.nvim`
  - `iamcco/markdown-preview.nvim`
- Keep behavior close to the current setup:
  - preserve display, clipboard, indentation, search, and filetype options
  - keep OneDarkPro as the colorscheme
  - keep Tree-sitter highlighting and indent setup
- Configure `markdown-preview.nvim` to lazy-load for Markdown buffers and commands.

## Migration Safety

- Back up the current `init.vim` before replacing it.
- Move the current `site/pack` directory out of the active runtime path to avoid duplicate plugin loading.
- Install plugins with `nvim --headless "+Lazy! sync" +qa`.

## Verification

- `nvim --headless "+Lazy! sync" +qa` completes successfully
- `nvim --headless "+Lazy! health" +qa` loads without config errors
- `nvim --headless "+lua print(vim.fn.exists(':MarkdownPreview'))" +qa` reports that the command exists
