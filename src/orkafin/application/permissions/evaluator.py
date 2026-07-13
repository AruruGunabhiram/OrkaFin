"""Deny-by-default authorization evaluation over independently trusted facts."""

from __future__ import annotations

from collections.abc import Iterable

from orkafin.application.permissions.models import (
    AuthorizationCheck,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationDecisionCode,
    RecordVisibilityGrant,
)
from orkafin.domain.base import Identifier, LowercaseIdentifier
from orkafin.domain.context import IdentityVerificationStatus, SelectedEntityRef
from orkafin.domain.identifiers import Permission

_SAFE_MESSAGES: dict[AuthorizationDecisionCode, str] = {
    AuthorizationDecisionCode.ALLOWED: "Access is allowed by current trusted authorization facts.",
    AuthorizationDecisionCode.IDENTITY_MISSING: (
        "Sign-in verification is required before this information can be shown."
    ),
    AuthorizationDecisionCode.IDENTITY_UNVERIFIED: (
        "Sign-in verification is required before this information can be shown."
    ),
    AuthorizationDecisionCode.TRUSTED_FACTS_MISSING: (
        "Access could not be verified for this request."
    ),
    AuthorizationDecisionCode.APP_ACCESS_DENIED: (
        "This area is not available for the verified account."
    ),
    AuthorizationDecisionCode.PAGE_ACCESS_DENIED: (
        "This area is not available for the verified account."
    ),
    AuthorizationDecisionCode.RECORD_ACCESS_DENIED: (
        "The requested candidate information is not available for the verified account."
    ),
    AuthorizationDecisionCode.FIELD_ACCESS_DENIED: (
        "The requested candidate information is not available for the verified account."
    ),
    AuthorizationDecisionCode.ACTION_ACCESS_DENIED: (
        "This action is not available for the verified account."
    ),
    AuthorizationDecisionCode.PERMISSION_MISSING: (
        "Required access could not be verified for this request."
    ),
    AuthorizationDecisionCode.PERMISSION_UNKNOWN: (
        "Required access could not be verified for this request."
    ),
}


class PermissionEvaluator:
    """Evaluate every scope from explicit grants; roles never create grants."""

    def __init__(self, *, known_permissions: Iterable[Permission]) -> None:
        self._known_permissions = frozenset(permission.root for permission in known_permissions)

    @property
    def known_permission_ids(self) -> tuple[str, ...]:
        """Return deterministic permission vocabulary, not a grant list."""
        return tuple(sorted(self._known_permissions))

    def check_app(
        self, context: AuthorizationContext, *, app_id: LowercaseIdentifier
    ) -> AuthorizationDecision:
        """Require verified identity plus an explicit trusted app-access fact."""
        return self._check_base(context, app_id=app_id, check=AuthorizationCheck.APP)

    def check_page(
        self,
        context: AuthorizationContext,
        *,
        app_id: LowercaseIdentifier,
        page_id: LowercaseIdentifier,
    ) -> AuthorizationDecision:
        """Require app access and an explicit page grant."""
        base = self._check_base(context, app_id=app_id, check=AuthorizationCheck.PAGE)
        if not base.allowed:
            return base
        facts = context.facts
        assert facts is not None
        if page_id not in facts.allowed_page_ids:
            return self._deny(AuthorizationCheck.PAGE, AuthorizationDecisionCode.PAGE_ACCESS_DENIED)
        return self._allow(AuthorizationCheck.PAGE)

    def check_permission(
        self,
        context: AuthorizationContext,
        *,
        app_id: LowercaseIdentifier,
        permission: Permission,
    ) -> AuthorizationDecision:
        """Require a known permission name and an explicit adapter grant."""
        base = self._check_base(context, app_id=app_id, check=AuthorizationCheck.PERMISSION)
        if not base.allowed:
            return base
        return self._check_permission_grant(
            context,
            permission=permission,
            check=AuthorizationCheck.PERMISSION,
        )

    def check_record(
        self,
        context: AuthorizationContext,
        *,
        record: SelectedEntityRef,
        required_permission: Permission | None = None,
    ) -> AuthorizationDecision:
        """Require an explicit record grant and, when supplied, a permission grant."""
        base = self._check_base(
            context,
            app_id=record.app_id,
            check=AuthorizationCheck.RECORD,
        )
        if not base.allowed:
            return base
        if required_permission is not None:
            permission = self._check_permission_grant(
                context,
                permission=required_permission,
                check=AuthorizationCheck.RECORD,
            )
            if not permission.allowed:
                return permission
        if self._record_grant(context, record) is None:
            return self._deny(
                AuthorizationCheck.RECORD,
                AuthorizationDecisionCode.RECORD_ACCESS_DENIED,
            )
        return self._allow(AuthorizationCheck.RECORD)

    def check_field(
        self,
        context: AuthorizationContext,
        *,
        record: SelectedEntityRef,
        field_id: Identifier,
        required_permission: Permission | None = None,
    ) -> AuthorizationDecision:
        """Require record visibility plus a per-record field allowlist entry."""
        record_decision = self.check_record(
            context,
            record=record,
            required_permission=required_permission,
        )
        if not record_decision.allowed:
            return self._reframe(record_decision, AuthorizationCheck.FIELD)
        grant = self._record_grant(context, record)
        assert grant is not None
        if field_id not in grant.visible_field_ids:
            return self._deny(
                AuthorizationCheck.FIELD,
                AuthorizationDecisionCode.FIELD_ACCESS_DENIED,
            )
        return self._allow(AuthorizationCheck.FIELD)

    def check_action(
        self,
        context: AuthorizationContext,
        *,
        app_id: LowercaseIdentifier,
        action_id: LowercaseIdentifier,
        required_permission: Permission,
        target: SelectedEntityRef | None = None,
    ) -> AuthorizationDecision:
        """Require explicit permission, advertised availability, and target visibility."""
        base = self._check_base(context, app_id=app_id, check=AuthorizationCheck.ACTION)
        if not base.allowed:
            return base
        permission = self._check_permission_grant(
            context,
            permission=required_permission,
            check=AuthorizationCheck.ACTION,
        )
        if not permission.allowed:
            return permission
        facts = context.facts
        assert facts is not None
        if action_id not in facts.available_action_ids:
            return self._deny(
                AuthorizationCheck.ACTION,
                AuthorizationDecisionCode.ACTION_ACCESS_DENIED,
            )
        if target is not None and self._record_grant(context, target) is None:
            return self._deny(
                AuthorizationCheck.ACTION,
                AuthorizationDecisionCode.RECORD_ACCESS_DENIED,
            )
        return self._allow(AuthorizationCheck.ACTION)

    def _check_base(
        self,
        context: AuthorizationContext,
        *,
        app_id: str,
        check: AuthorizationCheck,
    ) -> AuthorizationDecision:
        identity = context.identity
        if identity is None:
            return self._deny(check, AuthorizationDecisionCode.IDENTITY_MISSING)
        if identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            return self._deny(check, AuthorizationDecisionCode.IDENTITY_UNVERIFIED)
        facts = context.facts
        if facts is None:
            return self._deny(check, AuthorizationDecisionCode.TRUSTED_FACTS_MISSING)
        if (
            identity.role is None
            or identity.role.owner_app_id != app_id
            or facts.app_id != app_id
            or not facts.app_access
        ):
            return self._deny(check, AuthorizationDecisionCode.APP_ACCESS_DENIED)
        return self._allow(check)

    def _check_permission_grant(
        self,
        context: AuthorizationContext,
        *,
        permission: Permission,
        check: AuthorizationCheck,
    ) -> AuthorizationDecision:
        if permission.root not in self._known_permissions:
            return self._deny(check, AuthorizationDecisionCode.PERMISSION_UNKNOWN)
        facts = context.facts
        assert facts is not None
        if permission.root not in {value.root for value in facts.permissions}:
            return self._deny(check, AuthorizationDecisionCode.PERMISSION_MISSING)
        return self._allow(check)

    @staticmethod
    def _record_grant(
        context: AuthorizationContext, record: SelectedEntityRef
    ) -> RecordVisibilityGrant | None:
        facts = context.facts
        if facts is None:
            return None
        for grant in facts.records:
            if grant.record == record:
                return grant
        return None

    @staticmethod
    def _allow(check: AuthorizationCheck) -> AuthorizationDecision:
        return AuthorizationDecision(
            check=check,
            allowed=True,
            code=AuthorizationDecisionCode.ALLOWED,
            safe_message=_SAFE_MESSAGES[AuthorizationDecisionCode.ALLOWED],
        )

    @staticmethod
    def _deny(check: AuthorizationCheck, code: AuthorizationDecisionCode) -> AuthorizationDecision:
        return AuthorizationDecision(
            check=check,
            allowed=False,
            code=code,
            safe_message=_SAFE_MESSAGES[code],
        )

    @staticmethod
    def _reframe(
        decision: AuthorizationDecision, check: AuthorizationCheck
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            check=check,
            allowed=decision.allowed,
            code=decision.code,
            safe_message=decision.safe_message,
        )
