# Neovim lazy.nvim Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the user's Neovim plugin management from native `pack/*/start` to `lazy.nvim` and add `markdown-preview.nvim`.

**Architecture:** Keep `init.vim` as the user-facing entry point, bootstrap `lazy.nvim` from it, and move plugin declarations into `lua/plugins.lua`. Preserve the user's current runtime behavior while replacing manual plugin directories with `lazy.nvim`-managed installs.

**Tech Stack:** Neovim `v0.11.6`, Vimscript, Lua, `lazy.nvim`, `nvim-treesitter`, `onedarkpro.nvim`, `markdown-preview.nvim`

---

### Task 1: Prepare migrated config files

**Files:**
- Create: `~/.config/nvim/lua/plugins.lua`
- Modify: `~/.config/nvim/init.vim`

- [ ] **Step 1: Write the new `init.vim` content**

Add the existing editor options, then append `lazy.nvim` bootstrap code and `require("lazy").setup(...)`.

- [ ] **Step 2: Write `lua/plugins.lua`**

Define plugin specs for:
- `olimorris/onedarkpro.nvim`
- `nvim-treesitter/nvim-treesitter`
- `iamcco/markdown-preview.nvim`

- [ ] **Step 3: Review for behavior regressions**

Confirm that colorscheme setup moved into the colorscheme plugin config and Tree-sitter setup moved into the Tree-sitter plugin config.

### Task 2: Safely replace the live Neovim config

**Files:**
- Modify: `~/.config/nvim/init.vim`
- Create: `~/.config/nvim/lua/plugins.lua`

- [ ] **Step 1: Back up the old config**

Copy the current `init.vim` to a dated backup file.

- [ ] **Step 2: Disable the old native package directories**

Move `~/.local/share/nvim/site/pack` to a dated backup path so those plugins are not auto-loaded alongside `lazy.nvim`.

- [ ] **Step 3: Copy the migrated files into place**

Write the new `init.vim` and `lua/plugins.lua` into `~/.config/nvim/`.

### Task 3: Install and verify plugins

**Files:**
- Create: `~/.config/nvim/lazy-lock.json`

- [ ] **Step 1: Install and sync plugins**

Run: `nvim --headless "+Lazy! sync" +qa`

Expected: lazy.nvim bootstraps itself, installs configured plugins, runs plugin build steps, and exits cleanly.

- [ ] **Step 2: Verify the config loads**

Run: `nvim --headless "+Lazy! health" +qa`

Expected: no startup errors.

- [ ] **Step 3: Verify Markdown preview command exists**

Run: `nvim --headless "+lua print(vim.fn.exists(':MarkdownPreview'))" +qa`

Expected: prints `2`.
