"""Versioned built-in competition experience library."""

from .cases import CompetitionExperienceError, CompetitionExperienceLibrary
from .library import (
    DEFAULT_BUNDLED_ROOT,
    DEFAULT_INSTALL_ROOT,
    ExperienceLibraryError,
    ExperienceLibraryManager,
    ExperienceLibraryResolution,
    build_experience_package,
    write_library_manifest,
)

__all__ = [
    "CompetitionExperienceError",
    "CompetitionExperienceLibrary",
    "DEFAULT_BUNDLED_ROOT",
    "DEFAULT_INSTALL_ROOT",
    "ExperienceLibraryError",
    "ExperienceLibraryManager",
    "ExperienceLibraryResolution",
    "build_experience_package",
    "write_library_manifest",
]
