from sqlalchemy.orm import Session

from fpg_lab.services.p01b import P01BService


class P01CService(P01BService):
    def __init__(self, session: Session, codec: object | None = None) -> None:
        super().__init__(session, codec, flow="p01c")
