"""Pydantic request and response schemas with input validation."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


REGISTRATION_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{6,15}$")
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
SLOT_PATTERN = re.compile(r"^[A-Z]{1,4}-?\d{1,4}$")


def clean_registration(value: str) -> str:
    """Normalize and validate an Indian-style vehicle registration string."""
    normalized = re.sub(r"[\s-]", "", value).upper()

    if not REGISTRATION_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Enter a valid registration containing letters and digits, "
            "for example DL10AB1234."
        )

    return normalized


class SlotCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    zone: str = Field(default="Block A", min_length=2, max_length=40)
    slot_type: str = Field(default="car", pattern=r"^(car|bike|suv)$")

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not SLOT_PATTERN.fullmatch(value):
            raise ValueError("Use a slot code such as A12 or B-04.")
        return value

    @field_validator("zone")
    @classmethod
    def validate_zone(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]{1,39}", value):
            raise ValueError(
                "Zone must start with a letter and contain only letters, "
                "numbers or spaces."
            )
        return value


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    zone: str
    status: str
    slot_type: str


class VehicleCreate(BaseModel):
    registration_number: str = Field(min_length=6, max_length=20)
    owner_name: str = Field(min_length=2, max_length=100)
    phone: str = ""
    vehicle_type: str = Field(
        default="car", pattern=r"^(car|bike|suv|other)$"
    )

    @field_validator("registration_number")
    @classmethod
    def validate_registration(cls, value: str) -> str:
        return clean_registration(value)

    @field_validator("owner_name")
    @classmethod
    def validate_owner_name(cls, value: str) -> str:
        value = value.strip()
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Name must contain alphabets, spaces, apostrophes, dots "
                "or hyphens only."
            )
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValueError(
                "Enter a valid 10-digit Indian mobile number."
            )
        return value


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    registration_number: str
    owner_name: str
    phone: str
    vehicle_type: str


class BookingCreate(BaseModel):
    vehicle_number: str
    customer_name: str
    slot_id: int
    start_time: datetime
    end_time: datetime

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        return clean_registration(value)

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, value: str) -> str:
        value = value.strip()
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid customer name.")
        return value

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, value: datetime, info):
        start_time = info.data.get("start_time")
        if start_time and value <= start_time:
            raise ValueError("End time must be later than start time.")
        return value


# ---------------------------------------------------------------------------
# Authentication / user schemas
# ---------------------------------------------------------------------------


class UserRegister(BaseModel):
    """Schema for new-user registration."""

    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=255)
    phone: str = ""
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Name must contain alphabets, spaces, apostrophes, "
                "dots or hyphens only."
            )
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            value,
        ):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValueError(
                "Enter a valid 10-digit Indian mobile number."
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least one uppercase letter."
            )
        if not re.search(r"[a-z]", value):
            raise ValueError(
                "Password must contain at least one lowercase letter."
            )
        if not re.search(r"\d", value):
            raise ValueError(
                "Password must contain at least one digit."
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise ValueError(
                "Password must contain at least one special character."
            )
        return value


class UserLogin(BaseModel):
    """Schema for user login."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    """Public-facing user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str
    role: str


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile details."""

    full_name: str = Field(min_length=2, max_length=100)
    phone: str = ""

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid name.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValueError(
                "Enter a valid 10-digit Indian mobile number."
            )
        return value


class PasswordChange(BaseModel):
    """Schema for changing a user password."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least one uppercase letter."
            )
        if not re.search(r"[a-z]", value):
            raise ValueError(
                "Password must contain at least one lowercase letter."
            )
        if not re.search(r"\d", value):
            raise ValueError(
                "Password must contain at least one digit."
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise ValueError(
                "Password must contain at least one special character."
            )
        return value


class CustomerBookingCreate(BaseModel):
    """Schema for a customer creating their own booking."""

    vehicle_number: str
    slot_id: int
    start_time: datetime
    end_time: datetime

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        return clean_registration(value)

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, value: datetime, info):
        start_time = info.data.get("start_time")
        if start_time and value <= start_time:
            raise ValueError("End time must be later than start time.")
        return value

