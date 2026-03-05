# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from urllib.parse import urlencode

# Django import
from django.http import HttpResponseRedirect
from django.views import View

# Module imports
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.keycloak import KeycloakOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.license.models import Instance
from plane.utils.path_validator import validate_next_path


class KeycloakOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(validate_next_path(next_path))

        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            params = exc.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}?{urlencode(params)}")

        try:
            state = uuid.uuid4().hex
            provider = KeycloakOAuthProvider(request=request, state=state, is_space=True)
            request.session["state"] = state
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            params = e.get_error_dict()
            if next_path:
                params["next_path"] = str(next_path)
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}?{urlencode(params)}")


class KeycloakCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        next_path = request.session.get("next_path")

        if state != request.session.get("state", ""):
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_OAUTH_PROVIDER_ERROR"],
                error_message="KEYCLOAK_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}?{urlencode(params)}")

        if not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_OAUTH_PROVIDER_ERROR"],
                error_message="KEYCLOAK_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}?{urlencode(params)}")

        try:
            provider = KeycloakOAuthProvider(request=request, code=code, is_space=True)
            user = provider.authenticate()
            user_login(request=request, user=user, is_space=True)
            url = f"{base_host(request=request, is_space=True)}{str(validate_next_path(next_path)) if next_path else ''}"
            return HttpResponseRedirect(url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            if next_path:
                params["next_path"] = str(validate_next_path(next_path))
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}?{urlencode(params)}")
