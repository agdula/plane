# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

import pytz
import requests

# Module imports
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.adapter.oauth import OauthAdapter
from plane.license.utils.instance_value import get_configuration_value


class KeycloakOAuthProvider(OauthAdapter):
    provider = "keycloak"
    scope = "openid email profile"

    def __init__(self, request, code=None, state=None, callback=None, is_space=False):
        KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET, KEYCLOAK_ISSUER = get_configuration_value(
            [
                {"key": "KEYCLOAK_CLIENT_ID", "default": os.environ.get("KEYCLOAK_CLIENT_ID")},
                {"key": "KEYCLOAK_CLIENT_SECRET", "default": os.environ.get("KEYCLOAK_CLIENT_SECRET")},
                {"key": "KEYCLOAK_ISSUER", "default": os.environ.get("KEYCLOAK_ISSUER")},
            ]
        )

        if not (KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET and KEYCLOAK_ISSUER):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        parsed = urlparse(KEYCLOAK_ISSUER)
        if not parsed.scheme or parsed.scheme not in ("https", "http"):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        issuer = KEYCLOAK_ISSUER.rstrip("/")
        discovery_url = f"{issuer}/.well-known/openid-configuration"

        try:
            response = requests.get(discovery_url)
            response.raise_for_status()
            oidc_config = response.json()
        except requests.RequestException:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        self.token_url = oidc_config.get("token_endpoint")
        self.userinfo_url = oidc_config.get("userinfo_endpoint")
        authorization_endpoint = oidc_config.get("authorization_endpoint")

        if not (self.token_url and self.userinfo_url and authorization_endpoint):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        callback_path = "spaces/keycloak/callback/" if is_space else "keycloak/callback/"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/auth/{callback_path}"
        url_params = {
            "client_id": KEYCLOAK_CLIENT_ID,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{authorization_endpoint}?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            KEYCLOAK_CLIENT_ID,
            self.scope,
            redirect_uri,
            auth_url,
            self.token_url,
            self.userinfo_url,
            KEYCLOAK_CLIENT_SECRET,
            code,
            callback=callback,
        )

    def set_token_data(self):
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Accept": "application/json"}
        token_response = self.get_user_token(data=data, headers=headers)
        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("expires_in"))
                    if token_response.get("expires_in")
                    else None
                ),
                "refresh_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("refresh_expires_in"))
                    if token_response.get("refresh_expires_in")
                    else None
                ),
                "id_token": token_response.get("id_token", ""),
            }
        )

    def set_user_data(self):
        user_info_response = self.get_user_response()
        first_name = user_info_response.get("given_name") or user_info_response.get("name") or ""
        last_name = user_info_response.get("family_name") or ""
        if not last_name and first_name and " " in first_name:
            parts = first_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1]

        super().set_user_data(
            {
                "email": user_info_response.get("email"),
                "user": {
                    "provider_id": str(user_info_response.get("sub")),
                    "email": user_info_response.get("email"),
                    "avatar": user_info_response.get("picture"),
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_password_autoset": True,
                },
            }
        )
