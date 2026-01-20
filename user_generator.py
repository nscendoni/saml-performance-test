"""
User Generator Module
Generates synthetic user data for SAML performance testing
"""

import uuid
import random
import string
from dataclasses import dataclass, field
from typing import List, Optional, Iterator


@dataclass
class TestUser:
    """Represents a test user for SAML assertions"""
    user_id: str
    email: str
    groups: List[str] = field(default_factory=list)
    first_name: str = ""
    last_name: str = ""
    custom_attributes: dict = field(default_factory=dict)


class UserGenerator:
    """Generates test users for SAML performance testing"""

    # Sample data for generating realistic usernames
    FIRST_NAMES = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
        "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan",
        "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher",
        "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret",
        "Mark", "Sandra", "Donald", "Ashley", "Steven", "Kimberly", "Paul",
        "Emily", "Andrew", "Donna", "Joshua", "Michelle", "Kenneth", "Dorothy",
        "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa", "Timothy",
        "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    ]

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
        "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
        "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
        "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    ]

    DOMAINS = [
        "example.com", "test.org", "company.net", "corp.io", "enterprise.com",
        "acme.org", "testcorp.net", "demo.io", "sample.com", "testing.org",
    ]

    def __init__(
        self,
        domain: Optional[str] = None,
        default_groups: Optional[List[str]] = None,
        user_prefix: str = "user",
    ):
        """
        Initialize the user generator

        Args:
            domain: Email domain to use (default: random from DOMAINS)
            default_groups: Default groups to assign to all users
            user_prefix: Prefix for generated user IDs
        """
        self.domain = domain
        self.default_groups = default_groups or []
        self.user_prefix = user_prefix

    def _random_domain(self) -> str:
        """Get a random email domain"""
        return self.domain or random.choice(self.DOMAINS)

    def _random_string(self, length: int = 8) -> str:
        """Generate a random alphanumeric string"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_user(
        self,
        index: Optional[int] = None,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> TestUser:
        """
        Generate a single test user

        Args:
            index: Optional index for deterministic user ID
            groups: Optional groups (uses default_groups if not provided)
            custom_attributes: Optional custom attributes

        Returns:
            TestUser instance
        """
        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)

        if index is not None:
            user_id = f"{self.user_prefix}_{index:06d}"
        else:
            user_id = f"{self.user_prefix}_{self._random_string()}"

        domain = self._random_domain()
        email = f"{first_name.lower()}.{last_name.lower()}_{self._random_string(4)}@{domain}"

        user_groups = groups if groups is not None else self.default_groups.copy()

        return TestUser(
            user_id=user_id,
            email=email,
            groups=user_groups,
            first_name=first_name,
            last_name=last_name,
            custom_attributes=custom_attributes or {},
        )

    def generate_users(
        self,
        count: int,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> List[TestUser]:
        """
        Generate multiple test users

        Args:
            count: Number of users to generate
            groups: Optional groups to assign to all users
            custom_attributes: Optional custom attributes for all users

        Returns:
            List of TestUser instances
        """
        return [
            self.generate_user(
                index=i,
                groups=groups,
                custom_attributes=custom_attributes,
            )
            for i in range(count)
        ]

    def generate_users_iterator(
        self,
        count: int,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> Iterator[TestUser]:
        """
        Generate test users as an iterator (memory efficient for large counts)

        Args:
            count: Number of users to generate
            groups: Optional groups to assign to all users
            custom_attributes: Optional custom attributes for all users

        Yields:
            TestUser instances
        """
        for i in range(count):
            yield self.generate_user(
                index=i,
                groups=groups,
                custom_attributes=custom_attributes,
            )

    def generate_unique_user(self) -> TestUser:
        """
        Generate a user with a UUID-based unique identifier

        Returns:
            TestUser with UUID-based user_id
        """
        unique_id = str(uuid.uuid4())
        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)
        domain = self._random_domain()

        return TestUser(
            user_id=f"{self.user_prefix}_{unique_id}",
            email=f"{first_name.lower()}.{last_name.lower()}@{domain}",
            groups=self.default_groups.copy(),
            first_name=first_name,
            last_name=last_name,
        )


class SequentialUserGenerator:
    """Generates users with sequential, predictable IDs"""

    def __init__(
        self,
        user_id_pattern: str = "testuser_{index}",
        email_pattern: str = "testuser_{index}@test.example.com",
        default_groups: Optional[List[str]] = None,
    ):
        """
        Initialize with patterns for user generation

        Args:
            user_id_pattern: Pattern for user ID (use {index} as placeholder)
            email_pattern: Pattern for email (use {index} as placeholder)
            default_groups: Default groups for all users
        """
        self.user_id_pattern = user_id_pattern
        self.email_pattern = email_pattern
        self.default_groups = default_groups or []
        self._counter = 0

    def next_user(
        self,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> TestUser:
        """
        Generate the next user in sequence

        Args:
            groups: Optional groups (uses default if not provided)
            custom_attributes: Optional custom attributes

        Returns:
            TestUser instance
        """
        index = self._counter
        self._counter += 1

        return TestUser(
            user_id=self.user_id_pattern.format(index=index),
            email=self.email_pattern.format(index=index),
            groups=groups if groups is not None else self.default_groups.copy(),
            custom_attributes=custom_attributes or {},
        )

    def reset(self):
        """Reset the counter to 0"""
        self._counter = 0

    def generate_batch(
        self,
        count: int,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> List[TestUser]:
        """
        Generate a batch of sequential users

        Args:
            count: Number of users to generate
            groups: Optional groups for all users
            custom_attributes: Optional custom attributes

        Returns:
            List of TestUser instances
        """
        return [
            self.next_user(groups=groups, custom_attributes=custom_attributes)
            for _ in range(count)
        ]
