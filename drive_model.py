from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class PdfFile:
    name: str
    modified_time: str
    link: str


@dataclass
class ProgramFolder:
    name: str
    modified_time: str
    files: List[PdfFile] = field(default_factory=list)
    comment: Optional[str] = None


@dataclass
class InstrumentFolder:
    name: str
    modified_time: str
    programs: List[ProgramFolder] = field(default_factory=list)


@dataclass
class DriveLibrary:
    instruments: List[InstrumentFolder] = field(default_factory=list)
    last_updated: str = datetime.now().strftime("%d.%m.%Y %H:%M")
