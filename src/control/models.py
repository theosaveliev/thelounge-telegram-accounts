from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["FilebrowserAccount", "TelegramAccount", "TheloungeAccount"]


class Base(DeclarativeBase):
    pass


class RootAccountMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    updated: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ServiceAccountMixin(RootAccountMixin):
    password: Mapped[str] = mapped_column(String(60), nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False)


class TelegramAccount(RootAccountMixin, Base):
    __tablename__ = "telegram_accounts"

    meta: Mapped[str] = mapped_column(Text(), index=True, nullable=False)


class TheloungeAccount(ServiceAccountMixin, Base):
    __tablename__ = "thelounge_accounts"


class FilebrowserAccount(ServiceAccountMixin, Base):
    __tablename__ = "filebrowser_accounts"
