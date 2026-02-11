from sqlalchemy import (
    Column, Integer, Text, Boolean
)
from sqlalchemy.dialects.postgresql import ARRAY
from cps.forum.database.models import Base
class Emoji(Base):
    __tablename__ = "forum_emojis"

    id = Column(Integer, primary_key=True)
    annotation = Column(Text, nullable=False)
    emoji = Column(Text, nullable=False)

    group = Column(Text)
    subgroup = Column(Text)
    hexcode = Column(Text)
    unicode = Column(Integer)
    order = Column(Integer)

    directional = Column(Boolean, default=False)
    variation = Column(Boolean, default=False)

    emoticons = Column(ARRAY(Text))
    shortcodes = Column(ARRAY(Text))
    tags = Column(ARRAY(Text))

    skintone = Column(Text, nullable=True)
    skintone_base = Column(Text, nullable=True)
    skintone_combination = Column(Text, nullable=True)
    variation_base = Column(Text, nullable=True)
