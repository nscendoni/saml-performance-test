"""
SAML Assertion Builder Module
Builds and signs SAML 2.0 assertions for performance testing
"""

import uuid
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from lxml import etree
from signxml import XMLSigner, methods
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


# SAML Namespaces
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XS_NS = "http://www.w3.org/2001/XMLSchema"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

NSMAP = {
    "saml": SAML_NS,
    "samlp": SAMLP_NS,
    "ds": DS_NS,
    "xs": XS_NS,
    "xsi": XSI_NS,
}


class SAMLAssertionBuilder:
    """Builds SAML 2.0 assertions with configurable attributes"""

    def __init__(
        self,
        issuer: str,
        sp_url: str,
        private_key_path: str,
        certificate_path: str,
        assertion_lifetime_seconds: int = 300,
    ):
        self.issuer = issuer
        self.sp_url = sp_url
        self.assertion_lifetime = assertion_lifetime_seconds

        # Load private key
        with open(private_key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

        # Load certificate
        with open(certificate_path, "rb") as f:
            self.certificate = f.read()

    def _generate_id(self) -> str:
        """Generate a unique SAML ID"""
        return f"_id{uuid.uuid4().hex}"

    def _get_instant(self) -> str:
        """Get current UTC timestamp in SAML format"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _get_not_on_or_after(self) -> str:
        """Get expiration timestamp"""
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.assertion_lifetime)
        return expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

    def build_assertion(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
    ) -> etree._Element:
        """
        Build a SAML 2.0 Assertion

        Args:
            user_id: The user identifier (NameID)
            user_email: Optional user email
            groups: Optional list of group names
            custom_attributes: Optional dict of additional attributes

        Returns:
            lxml Element containing the assertion
        """
        now = self._get_instant()
        not_on_or_after = self._get_not_on_or_after()
        assertion_id = self._generate_id()

        # Create Assertion root element
        assertion = etree.Element(
            f"{{{SAML_NS}}}Assertion",
            nsmap={"saml": SAML_NS},
            attrib={
                "ID": assertion_id,
                "IssueInstant": now,
                "Version": "2.0",
            },
        )

        # Issuer
        issuer_elem = etree.SubElement(assertion, f"{{{SAML_NS}}}Issuer")
        issuer_elem.text = self.issuer

        # Subject
        subject = etree.SubElement(assertion, f"{{{SAML_NS}}}Subject")
        name_id = etree.SubElement(
            subject,
            f"{{{SAML_NS}}}NameID",
            attrib={
                "Format": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
            },
        )
        name_id.text = user_id

        subject_confirmation = etree.SubElement(
            subject,
            f"{{{SAML_NS}}}SubjectConfirmation",
            attrib={"Method": "urn:oasis:names:tc:SAML:2.0:cm:bearer"},
        )
        etree.SubElement(
            subject_confirmation,
            f"{{{SAML_NS}}}SubjectConfirmationData",
            attrib={
                "NotOnOrAfter": not_on_or_after,
                "Recipient": self.sp_url,
            },
        )

        # Conditions
        conditions = etree.SubElement(
            assertion,
            f"{{{SAML_NS}}}Conditions",
            attrib={
                "NotBefore": now,
                "NotOnOrAfter": not_on_or_after,
            },
        )
        audience_restriction = etree.SubElement(
            conditions, f"{{{SAML_NS}}}AudienceRestriction"
        )
        audience = etree.SubElement(audience_restriction, f"{{{SAML_NS}}}Audience")
        audience.text = self.sp_url

        # AuthnStatement
        authn_statement = etree.SubElement(
            assertion,
            f"{{{SAML_NS}}}AuthnStatement",
            attrib={
                "AuthnInstant": now,
                "SessionIndex": self._generate_id(),
            },
        )
        authn_context = etree.SubElement(
            authn_statement, f"{{{SAML_NS}}}AuthnContext"
        )
        authn_context_class_ref = etree.SubElement(
            authn_context, f"{{{SAML_NS}}}AuthnContextClassRef"
        )
        authn_context_class_ref.text = (
            "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
        )

        # AttributeStatement
        attr_statement = etree.SubElement(assertion, f"{{{SAML_NS}}}AttributeStatement")

        # Add user ID attribute
        self._add_attribute(attr_statement, "uid", user_id)

        # Add email if provided
        if user_email:
            self._add_attribute(attr_statement, "email", user_email)

        # Add groups if provided
        if groups:
            for group in groups:
                self._add_attribute(attr_statement, "groups", group)

        # Add custom attributes
        if custom_attributes:
            for name, value in custom_attributes.items():
                if isinstance(value, list):
                    for v in value:
                        self._add_attribute(attr_statement, name, str(v))
                else:
                    self._add_attribute(attr_statement, name, str(value))

        return assertion

    def _add_attribute(
        self, parent: etree._Element, name: str, value: str
    ) -> etree._Element:
        """Add a SAML attribute to the AttributeStatement"""
        attr = etree.SubElement(
            parent,
            f"{{{SAML_NS}}}Attribute",
            attrib={
                "Name": name,
                "NameFormat": "urn:oasis:names:tc:SAML:2.0:attrname-format:basic",
            },
        )
        attr_value = etree.SubElement(
            attr,
            f"{{{SAML_NS}}}AttributeValue",
            attrib={f"{{{XSI_NS}}}type": "xs:string"},
            nsmap={"xs": XS_NS, "xsi": XSI_NS},
        )
        attr_value.text = value
        return attr

    def build_response(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
        in_response_to: Optional[str] = None,
    ) -> etree._Element:
        """
        Build a complete SAML Response containing the assertion

        Args:
            user_id: The user identifier
            user_email: Optional user email
            groups: Optional list of groups
            custom_attributes: Optional custom attributes
            in_response_to: Optional request ID this responds to

        Returns:
            lxml Element containing the SAML Response
        """
        now = self._get_instant()
        response_id = self._generate_id()

        # Build the assertion first
        assertion = self.build_assertion(
            user_id=user_id,
            user_email=user_email,
            groups=groups,
            custom_attributes=custom_attributes,
        )

        # Create Response element
        response_attrib = {
            "ID": response_id,
            "IssueInstant": now,
            "Version": "2.0",
            "Destination": self.sp_url,
        }
        if in_response_to:
            response_attrib["InResponseTo"] = in_response_to

        response = etree.Element(
            f"{{{SAMLP_NS}}}Response",
            nsmap={"samlp": SAMLP_NS, "saml": SAML_NS},
            attrib=response_attrib,
        )

        # Issuer
        issuer_elem = etree.SubElement(response, f"{{{SAML_NS}}}Issuer")
        issuer_elem.text = self.issuer

        # Status
        status = etree.SubElement(response, f"{{{SAMLP_NS}}}Status")
        status_code = etree.SubElement(
            status,
            f"{{{SAMLP_NS}}}StatusCode",
            attrib={"Value": "urn:oasis:names:tc:SAML:2.0:status:Success"},
        )

        # Add the assertion
        response.append(assertion)

        return response

    def sign_assertion(self, assertion: etree._Element) -> etree._Element:
        """Sign a SAML assertion"""
        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        )

        signed = signer.sign(
            assertion,
            key=self.private_key,
            cert=self.certificate,
        )
        return signed

    def sign_response(self, response: etree._Element) -> etree._Element:
        """Sign a SAML response (signs the assertion within)"""
        # Find and sign the assertion first
        assertion = response.find(f".//{{{SAML_NS}}}Assertion")
        if assertion is not None:
            signed_assertion = self.sign_assertion(assertion)
            # Replace the unsigned assertion with signed one
            parent = assertion.getparent()
            parent.remove(assertion)
            parent.append(signed_assertion)

        return response

    def build_signed_response(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
        in_response_to: Optional[str] = None,
    ) -> str:
        """
        Build and sign a complete SAML Response, returning base64 encoded

        Returns:
            Base64 encoded SAML Response
        """
        response = self.build_response(
            user_id=user_id,
            user_email=user_email,
            groups=groups,
            custom_attributes=custom_attributes,
            in_response_to=in_response_to,
        )

        signed_response = self.sign_response(response)

        # Convert to string and base64 encode
        xml_string = etree.tostring(
            signed_response, encoding="unicode", pretty_print=False
        )
        return base64.b64encode(xml_string.encode("utf-8")).decode("utf-8")

    def build_signed_response_xml(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        groups: Optional[List[str]] = None,
        custom_attributes: Optional[dict] = None,
        in_response_to: Optional[str] = None,
    ) -> str:
        """
        Build and sign a complete SAML Response, returning XML string

        Returns:
            XML string of signed SAML Response
        """
        response = self.build_response(
            user_id=user_id,
            user_email=user_email,
            groups=groups,
            custom_attributes=custom_attributes,
            in_response_to=in_response_to,
        )

        signed_response = self.sign_response(response)

        return etree.tostring(
            signed_response, encoding="unicode", pretty_print=True
        )
