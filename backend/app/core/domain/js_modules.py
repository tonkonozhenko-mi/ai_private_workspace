"""The shape of a JavaScript/TypeScript codebase.

The graph could describe a Python project — modules, entrypoints, frameworks — and
knew nothing about the most common kind of repository there is. A developer opening
a TypeScript project got "TypeScript application" and a blank map.

Everything here is read from files: package.json says the name, the scripts and the
dependencies; the imports say which module leans on which. No model, no guessing.

Pure: no I/O, no state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# import x from "./y" · export … from "../z" · require("./y") · dynamic import("./y")
_IMPORT_RE = re.compile(
    r"""(?:from\s+|import\s*\(|require\s*\()\s*['"](?P<target>[^'"]+)['"]""",
)

# Frameworks worth naming in a one-line summary, keyed by the dependency that proves
# them. A project is "a Next.js application", not "a JavaScript application".
_FRAMEWORK_BY_DEPENDENCY = {
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "@angular/core": "Angular",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "fastify": "Fastify",
    "koa": "Koa",
    "electron": "Electron",
    "react-native": "React Native",
    "@tauri-apps/api": "Tauri",
}

# Dependencies that say something about how the project is built or tested, worth
# surfacing; the long tail of utility packages is not.
_NOTABLE_DEPENDENCIES = {
    "typescript",
    "vite",
    "webpack",
    "rollup",
    "esbuild",
    "jest",
    "vitest",
    "playwright",
    "cypress",
    "eslint",
    "prettier",
    "prisma",
    "typeorm",
    "sequelize",
    "knex",
    "graphql",
    "axios",
    "zod",
    "redux",
    "tailwindcss",
}

_ENTRYPOINT_NAMES = {
    "index.ts",
    "index.tsx",
    "index.js",
    "main.ts",
    "main.tsx",
    "main.js",
    "app.ts",
    "app.tsx",
    "server.ts",
    "server.js",
}

_JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}

_MAX_FILES = 1200


@dataclass(frozen=True)
class JsModule:
    name: str
    path: str
    internal_imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JsFacts:
    package_name: str | None = None
    frameworks: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    modules: list[JsModule] = field(default_factory=list)
    notable_dependencies: list[str] = field(default_factory=list)
    scripts: dict[str, str] = field(default_factory=dict)
    manifest_files: list[str] = field(default_factory=list)
    files_count: int = 0


def _module_name(path: str) -> str:
    """`frontend/src/components/AskWorkspace.tsx` → `components/AskWorkspace`.

    The directory above the file is kept because a bare `index` or `types` would be
    meaningless — half a dozen of them exist in any real project.
    """
    posix = PurePosixPath(path)
    stem = posix.stem
    parent = posix.parent.name
    return f"{parent}/{stem}" if parent else stem


def _resolve_relative(importer: str, target: str) -> str | None:
    """`./sibling` and `../up/one` resolved against the importing file's directory, so
    an import can be matched to the module it actually points at. Package imports
    (`react`, `@scope/x`) are not modules of this project and return None."""
    if not target.startswith("."):
        return None
    base = PurePosixPath(importer).parent
    parts = list(base.parts)
    for segment in target.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    if not parts:
        return None
    resolved = "/".join(parts)
    # Strip an explicit extension so it matches the module naming above.
    return re.sub(r"\.(ts|tsx|js|jsx|mjs|cjs|vue|svelte)$", "", resolved)


def parse_package_json(content: str) -> tuple[str | None, dict[str, str], list[str], list[str]]:
    """(name, scripts, frameworks, notable dependencies) from one package.json."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None, {}, [], []
    if not isinstance(data, dict):
        return None, {}, [], []

    dependencies: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = data.get(key)
        if isinstance(value, dict):
            dependencies.update({str(k): str(v) for k, v in value.items()})

    frameworks = [
        label
        for dependency, label in _FRAMEWORK_BY_DEPENDENCY.items()
        if dependency in dependencies
    ]
    notable = sorted(name for name in dependencies if name in _NOTABLE_DEPENDENCIES)
    scripts = data.get("scripts")
    scripts = (
        {str(k): str(v) for k, v in scripts.items()} if isinstance(scripts, dict) else {}
    )
    name = data.get("name")
    return (str(name) if name else None), scripts, frameworks, notable


def build_js_facts(files: dict[str, str]) -> JsFacts:
    """``files`` is {path: content} for the project's JS/TS sources and package.json."""
    manifests = sorted(p for p in files if PurePosixPath(p).name == "package.json")
    source_paths = sorted(
        p
        for p in files
        if PurePosixPath(p).suffix in _JS_SUFFIXES
    )[:_MAX_FILES]

    package_name: str | None = None
    scripts: dict[str, str] = {}
    frameworks: list[str] = []
    notable: list[str] = []
    for manifest in manifests:
        name, manifest_scripts, manifest_frameworks, manifest_notable = parse_package_json(
            files[manifest]
        )
        package_name = package_name or name
        scripts = scripts or manifest_scripts
        for framework in manifest_frameworks:
            if framework not in frameworks:
                frameworks.append(framework)
        for dependency in manifest_notable:
            if dependency not in notable:
                notable.append(dependency)

    # Module name → path, so imports can be resolved to modules we actually have.
    by_resolved: dict[str, str] = {
        re.sub(r"\.(ts|tsx|js|jsx|mjs|cjs|vue|svelte)$", "", path): path
        for path in source_paths
    }

    modules: list[JsModule] = []
    entrypoints: list[str] = []
    for path in source_paths:
        content = files[path]
        if PurePosixPath(path).name in _ENTRYPOINT_NAMES:
            entrypoints.append(path)

        internal: list[str] = []
        for match in _IMPORT_RE.finditer(content):
            resolved = _resolve_relative(path, match.group("target"))
            if resolved is None:
                continue
            # An import of a directory means its index file.
            target_path = by_resolved.get(resolved) or by_resolved.get(f"{resolved}/index")
            if target_path and target_path != path:
                name = _module_name(target_path)
                if name not in internal:
                    internal.append(name)

        modules.append(JsModule(name=_module_name(path), path=path, internal_imports=internal))

    return JsFacts(
        package_name=package_name,
        frameworks=frameworks,
        entrypoints=sorted(entrypoints),
        modules=modules,
        notable_dependencies=notable,
        scripts=scripts,
        manifest_files=manifests,
        files_count=len(source_paths),
    )
