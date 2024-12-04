import os
import time
from enum import Enum
from typing import List, Optional, TypedDict
from typing_extensions import Required, NotRequired
import typing
from urllib.parse import urljoin
from uuid import UUID

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning


def parse_bool(value: str):
    return value.lower() not in ["false", "no", "0"]


verify_ssl = parse_bool(os.environ.get("REQUESTS_VERIFY_SSL", "true"))

requests_timeout = int(os.environ.get("REQUESTS_TIMEOUT", 15))

urllib3.disable_warnings(category=InsecureRequestWarning)


def is_uuid(value):
    try:
        UUID(value)
        return True
    except ValueError:
        return False


class WaldurClientException(Exception):
    pass


class ObjectDoesNotExist(WaldurClientException):
    """The requested object does not exist"""

    pass


class MultipleObjectsReturned(WaldurClientException):
    """The query returned multiple objects when only one was expected."""

    pass


class ValidationError(WaldurClientException):
    """An error while validating data."""

    pass


class TimeoutError(WaldurClientException):
    """Thrown when a command does not complete in enough time."""

    pass


class InvalidStateError(WaldurClientException):
    """Thrown when a resource transitions to the error state."""

    pass


class ComponentUsage(TypedDict):
    # TODO: rename to 'component_type' after https://opennode.atlassian.net/browse/WAL-4259 is done
    type: str
    amount: int
    description: str


class ResourceReportRecord(TypedDict):
    header: str
    body: str


class OfferingComponentBillingTypes:
    FIXED = "fixed"
    USAGE = "usage"
    ONE_TIME = "one"
    ON_PLAN_SWITCH = "few"
    LIMIT = "limit"


class OfferingComponentLimitPeriod:
    MONTH = "month"
    ANNUAL = "annual"
    TOTAL = "total"


class OfferingComponent(TypedDict):
    billing_type: Required[str]
    type: Required[str]
    name: Required[str]
    measured_unit: Required[str]
    uuid: str
    description: str
    limit_period: str
    limit_amount: int
    article_code: str
    max_value: int
    min_value: int
    is_boolean: bool
    default_limit: int


class AssignFloatingIpPair(TypedDict):
    url: str
    subnet: str


class AssignFloatingIpPayload(TypedDict):
    floating_ips: List[AssignFloatingIpPair]


class CreateComponentUsagePayload(TypedDict):
    usages: List[ComponentUsage]
    plan_period: NotRequired[str]
    resource: NotRequired[str]


class ListMarketplaceResourcesPayload(TypedDict):
    provider_uuid: NotRequired[str]
    project_uuid: NotRequired[str]
    state: NotRequired[str]
    offering_uuid: NotRequired[str]
    field: NotRequired[List[str]]


class UpdateInstancePortItem(TypedDict):
    subnet: str


class UpdateInstancePortsPayload(TypedDict):
    ports: List[UpdateInstancePortItem]


class ResourceState(Enum):
    OK = "ok"
    ERRED = "erred"
    TERMINATED = "terminated"


class SlurmAllocationState(Enum):
    CREATING = "creating"
    UPDATE_SCHEDULED = "update_scheduled"
    UPDATING = "updating"
    DELETION_SCHEDULED = "deletion_scheduled"
    DELETING = "deleting"
    OK = "ok"
    ERRED = "erred"


class PaymentProfileType(Enum):
    FIXED_PRICE = "fixed_price"
    MONTHLY_INVOICES = "invoices"
    PAYMENT_GW_MONTHLY = "payment_gw_monthly"


class InvoiceState(Enum):
    PENDING = "pending"
    CREATED = "created"
    PAID = "paid"
    CANCELED = "canceled"


class Endpoints:
    Configuration = "configuration"
    Customers = "customers"
    EventSubscriptions = "event-subscriptions"
    FreeIPAProfiles = "freeipa-profiles"
    Invoice = "invoices"
    InvoiceItems = "invoice-items"
    MarketplaceCategories = "marketplace-categories"
    MarketplaceComponentUsage = "marketplace-component-usages"
    MarketplaceOrder = "marketplace-orders"
    MarketplaceProviderOffering = "marketplace-provider-offerings"
    MarketplaceProviderPlan = "marketplace-plans"
    MarketplacePublicOffering = "marketplace-public-offerings"
    MarketplaceResources = "marketplace-resources"
    MarketplaceProviderResources = "marketplace-provider-resources"
    MarketplaceRobotAccount = "marketplace-robot-accounts"
    MarketplaceSlurm = "marketplace-slurm"
    MarketplaceSlurmRemote = "marketplace-slurm-remote"
    MarketplaceStats = "marketplace-stats"
    MarketplaceOfferingPermissions = "marketplace-offering-permissions"
    MarketplaceOfferingUsers = "marketplace-offering-users"
    OpenStackFlavor = "openstack-flavors"
    OpenStackFloatingIP = "openstack-floating-ips"
    OpenStackImage = "openstack-images"
    OpenStackInstance = "openstack-instances"
    OpenStackNetwork = "openstack-networks"
    OpenStackSecurityGroup = "openstack-security-groups"
    OpenStackServerGroup = "openstack-server-groups"
    OpenStackSnapshot = "openstack-snapshots"
    OpenStackSubnet = "openstack-subnets"
    OpenStackTenant = "openstack-tenants"
    OpenStackVolume = "openstack-volumes"
    OpenStackVolumeType = "openstack-volume-types"
    PaymentProfiles = "payment-profiles"
    Project = "projects"
    ProjectTypes = "project-types"
    Provider = "service-settings"
    RemoteEduteams = "remote-eduteams"
    Roles = "roles"
    MarketplaceServiceProviders = "marketplace-service-providers"
    SlurmAllocations = "slurm-allocations"
    SlurmAllocationUserUsages = "slurm-allocation-user-usages"
    SlurmAssociations = "slurm-associations"
    SshKey = "keys"
    SupportComments = "support-comments"
    SupportIssues = "support-issues"
    Users = "users"


class ResourceTypes:
    OpenStackInstance = "OpenStack.Instance"
    OpenStackVolume = "OpenStack.Volume"


class WaldurClient(object):
    marketplaceScopeEndpoints = {
        ResourceTypes.OpenStackInstance: Endpoints.OpenStackInstance,
        ResourceTypes.OpenStackVolume: Endpoints.OpenStackVolume,
    }

    def __init__(self, api_url, access_token, user_agent=None):
        """
        Initializes a Waldur client
        :param api_url: a fully qualified URL to the Waldur API. Example: https://waldur.example.com:8000/api
        :param access_token: an access token to be used to communicate with the API.
        """

        self.api_url = self._ensure_trailing_slash(api_url)
        self.headers = {
            "Authorization": "token %s" % access_token,
            "Content-Type": "application/json",
        }
        if user_agent is not None:
            self.headers["User-Agent"] = user_agent

    def _ensure_trailing_slash(self, url):
        return url if url[-1] == "/" else "%s/" % url

    def _build_url(self, endpoint, action=None):
        parts = [endpoint]
        if action:
            parts.append(action)
        return urljoin(self.api_url, self._ensure_trailing_slash("/".join(parts)))

    def _build_resource_url(
        self, endpoint, uid1, action=None, sub_endpoint=None, uid2=None
    ):
        if not uid1:
            raise WaldurClientException("Resource ID is empty.")
        parts = [endpoint, str(uid1)]

        if sub_endpoint is not None and uid2 is not None:
            parts.extend([sub_endpoint, str(uid2)])

        if action:
            parts.append(action)
        return self._build_url("/".join(parts))

    def _parse_error(self, response):
        reason = getattr(response, "reason")

        try:
            reason = "%s. %s" % (reason, response.json())
        except ValueError:
            pass

        details = "URL %s. Status: %s. Reason: %s." % (
            response.url,
            response.status_code,
            reason,
        )
        return "Server refuses to communicate. %s" % details

    def _make_request(
        self,
        method,
        url,
        valid_states,
        retry_count=3,
        prev_response_data=None,
        **kwargs,
    ):
        if retry_count == 0:
            raise WaldurClientException(
                "Reached a limit of retries for the operation: %s %s, body: %s"
                % (method, url, prev_response_data)
            )

        params = dict(headers=self.headers, verify=verify_ssl, timeout=requests_timeout)
        params.update(kwargs)

        try:
            response = getattr(requests, method)(url, **params)
        except requests.exceptions.RequestException as error:
            raise WaldurClientException(str(error))

        if method == "post" and response.status_code in [301, 302, 303, 307, 308]:
            redirect_url = response.headers["Location"]
            return self._make_request(
                method,
                redirect_url,
                valid_states,
                retry_count,
                **kwargs,
            )

        if response.status_code not in valid_states:
            # a special treatment for 409 response, which can be due to async operations
            if response.status_code == 409:
                time.sleep(2)  # wait for things to calm down
                return self._make_request(
                    method,
                    url,
                    valid_states,
                    retry_count - 1,
                    prev_response_data=response.text,
                    **kwargs,
                )
            raise WaldurClientException(self._parse_error(response))

        if method == "head":
            return response
        if response.text:
            return response.json()
        return ""

    def _get_all(self, url, **kwargs):
        auth_params = dict(
            headers=self.headers, verify=verify_ssl, timeout=requests_timeout
        )
        params = dict()
        params.update(auth_params)
        params.update(kwargs)

        try:
            response = requests.get(url, **params)
        except requests.exceptions.RequestException as error:
            raise WaldurClientException(str(error))

        if response.status_code != 200:
            raise WaldurClientException(self._parse_error(response))
        result = response.json()
        if "Link" not in response.headers:
            return result
        while "next" in response.headers["Link"]:
            if "prev" in response.headers["Link"]:
                next_url = response.headers["Link"].split(", ")[2].split("; ")[0][1:-1]
            else:  # First page case
                next_url = response.headers["Link"].split(", ")[1].split("; ")[0][1:-1]
            try:
                # filters are already included in the next_url so we only
                # need auth_params
                response = requests.get(next_url, **auth_params)
            except requests.exceptions.RequestException as error:
                raise WaldurClientException(str(error))

            if response.status_code != 200:
                raise WaldurClientException(self._parse_error(response))

            result += response.json()

        return result

    def _get_count(self, url, **kwargs):
        response = self._head(url, **kwargs)
        return int(response.headers["X-Result-Count"])

    def _get(self, url, valid_states, **kwargs):
        return self._make_request("get", url, valid_states, 1, **kwargs)

    def _head(self, url, **kwargs):
        return self._make_request("head", url, valid_states=[200], **kwargs)

    def _post(self, url, valid_states, **kwargs):
        return self._make_request(
            "post", url, valid_states, allow_redirects=False, **kwargs
        )

    def _put(self, url, valid_states, **kwargs):
        return self._make_request("put", url, valid_states, **kwargs)

    def _patch(self, url, valid_states, **kwargs):
        return self._make_request("patch", url, valid_states, **kwargs)

    def _delete(self, url, valid_states, **kwargs):
        return self._make_request("delete", url, valid_states, **kwargs)

    def _make_get_query(self, url, query_params, get_first=False, get_few=False):
        """
        Get object via Waldur API.

        :param url: URL.
        :param query_params: dict with query params.
        :param get_first: If True then will return the first result.
        :param get_few: If True then will return all results.

        Note:
        If get_first or get_few have been set, then multiple results are correct.
        In the first case, we get the first result, in the second case we get all results.
        If get_first or get_few have not been set, then multiple results are not correct.
        """

        result = self._get(url, valid_states=[200], params=query_params)
        if not result:
            message = "Result is empty. Endpoint: %s. Query: %s" % (url, query_params)
            raise ObjectDoesNotExist(message)

        if isinstance(result, dict):
            return result

        if len(result) > 1:
            if not get_first and not get_few:
                message = "Ambiguous result. Endpoint: %s. Query: %s" % (
                    url,
                    query_params,
                )
                raise MultipleObjectsReturned(message)
            elif get_few:
                return result

        return result if get_few else result[0]

    def _query_resource(self, endpoint, query_params, get_first=False):
        url = self._build_url(endpoint)
        if "uuid" in query_params:
            url += query_params.pop("uuid") + "/"

        return self._make_get_query(url, query_params, get_first)

    def _query_resource_by_uuid(self, endpoint, value, extra=None):
        payload = {"uuid": value}
        if extra:
            payload.update(extra)
        return self._query_resource(endpoint, payload)

    def _query_resource_by_name(self, endpoint, value, extra=None):
        payload = {"name_exact": value}
        if extra:
            payload.update(extra)
        return self._query_resource(endpoint, payload)

    def _query_resource_list(self, endpoint, query_params):
        url = self._build_url(endpoint)
        if query_params is None:
            query_params = {}
        query_params.setdefault("page_size", 200)
        return self._get_all(url, params=query_params)

    def _get_resource(self, endpoint, value, extra=None):
        """
        Get resource by UUID, name or query parameters.

        :param endpoint: WaldurClient.Endpoint attribute.
        :param value: name or uuid of the resource
        :return: a resource as a dictionary.
        :raises: WaldurClientException if resource could not be received or response failed.
        """
        if not value:
            raise WaldurClientException("Empty ID is not allowed.")
        if is_uuid(value):
            return self._query_resource_by_uuid(endpoint, value, extra)
        else:
            return self._query_resource_by_name(endpoint, value, extra)

    def _create_resource(self, endpoint, payload=None, valid_state=201):
        url = self._build_url(endpoint)
        return self._post(url, [valid_state], json=payload)

    def _update_resource(self, endpoint, uuid, payload):
        url = self._build_resource_url(endpoint, uuid)
        return self._put(url, [200], json=payload)

    def _patch_resource(self, endpoint, uuid, payload):
        url = self._build_resource_url(endpoint, uuid)
        return self._patch(url, [200], json=payload)

    def _delete_resource_by_url(self, url):
        return self._delete(url, [202, 204])

    def _delete_resource(self, endpoint, uuid):
        url = self._build_resource_url(endpoint, uuid)
        return self._delete_resource_by_url(url)

    def _execute_resource_action(self, endpoint, uuid, action, **kwargs):
        url = self._build_resource_url(endpoint, uuid, action)
        return self._post(url, [202], **kwargs)

    def _get_service_settings(self, identifier):
        return self._get_resource(Endpoints.Provider, identifier)

    def _get_project(self, identifier):
        return self._get_resource(Endpoints.Project, identifier)

    def get_configuration(self):
        return self._query_resource_list(Endpoints.Configuration, {})

    def get_user(self, identifier):
        return self._get_resource(Endpoints.Users, identifier)

    def list_users(self, filters=None):
        return self._query_resource_list(Endpoints.Users, filters)

    def get_current_user(self):
        url = self._build_url(Endpoints.Users, "me")
        return self._get(url, valid_states=[200])

    def list_freeipa_profiles(self, filters=None):
        return self._query_resource_list(Endpoints.FreeIPAProfiles, filters)

    def count_users(self, **kwargs):
        url = self._build_url(Endpoints.Users)
        return self._get_count(url, **kwargs)

    def get_roles(self, **kwargs):
        url = self._build_url(Endpoints.Roles)
        return self._get_all(url, **kwargs)

    def list_ssh_keys(self):
        url = self._build_url(Endpoints.SshKey)
        return self._get_all(url)

    def _get_property(self, endpoint, identifier, settings_uuid):
        query = {"settings_uuid": settings_uuid}
        if is_uuid(identifier):
            query["uuid"] = identifier
        else:
            query["name_exact"] = identifier
        return self._query_resource(endpoint, query)

    def _get_flavor(self, identifier, tenant_uuid):
        query = {"tenant_uuid": tenant_uuid}
        if is_uuid(identifier):
            query["uuid"] = identifier
        else:
            query["name_exact"] = identifier
        return self._query_resource(Endpoints.OpenStackFlavor, query)

    def _get_flavor_from_params(self, cpu, ram):
        query_params = {"o": "cores,ram,disk"}
        if cpu:
            query_params["cores__gte"] = cpu
        if ram:
            query_params["ram__gte"] = ram

        return self._query_resource(
            Endpoints.OpenStackFlavor, query_params, get_first=True
        )

    def _get_image(self, identifier, tenant_uuid):
        query = {"tenant_uuid": tenant_uuid}
        if is_uuid(identifier):
            query["uuid"] = identifier
        else:
            query["name_exact"] = identifier
        return self._query_resource(Endpoints.OpenStackImage, query)

    def _get_floating_ip(self, address):
        return self._query_resource(Endpoints.OpenStackFloatingIP, {"address": address})

    def _get_subnet(self, identifier):
        return self._get_resource(Endpoints.OpenStackSubnet, identifier)

    def _get_tenant_subnet_by_uuid(self, uuid):
        query = {
            "uuid": uuid,
        }
        return self._query_resource(Endpoints.OpenStackSubnet, query)

    def _get_volume_type(self, identifier, tenant_uuid):
        query = {"tenant_uuid": tenant_uuid}
        if is_uuid(identifier):
            query["uuid"] = identifier
        else:
            query["name_exact"] = identifier
        return self._query_resource(Endpoints.OpenStackVolumeType, query)

    def _networks_to_payload(self, networks):
        """
        Serialize networks. Input should be in the following format:
            {
                subnet: name or uuid
                floating_ip: auto or address or empty
            }
        :return: a tuple, where first argument is subnets and second is floating_ips.
        """
        subnets = []
        floating_ips = []

        for item in networks:
            if "subnet" not in item:
                raise ValidationError("Wrong networks format. subnet key is required.")
            subnet_resource = self._get_subnet(item["subnet"])
            subnet = {"subnet": subnet_resource["url"]}
            subnets.append(subnet)
            address = item.get("floating_ip")
            if address:
                ip = subnet.copy()
                if address != "auto":
                    floating_ip_resource = self._get_floating_ip(address)
                    ip.update({"url": floating_ip_resource["url"]})
                floating_ips.append(ip)

        return subnets, floating_ips

    def _get_tenant_security_group(self, tenant_uuid, name):
        query = {
            "name_exact": name,
            "tenant_uuid": tenant_uuid,
        }
        return self._query_resource(Endpoints.OpenStackSecurityGroup, query)

    def _get_tenant_security_groups(self, tenant_uuid):
        query = {"tenant_uuid": tenant_uuid}
        return self._query_resource_list(Endpoints.OpenStackSecurityGroup, query)

    def _is_resource_ready(self, endpoint, uuid):
        resource = self._query_resource_by_uuid(endpoint, uuid)
        if resource["state"] == "Erred":
            raise InvalidStateError("Resource is in erred state.")
        return resource["state"] == "OK"

    def _create_instance(self, payload):
        return self._create_resource(Endpoints.OpenStackInstance, payload)

    def _get_tenant(self, name, project=None):
        """
        Find OpenStack tenant resource in Waldur database.
        :param name: OpenStack name or UUID.
        :param project: Waldur project name or UUID.
        :return: OpenStack tenant as Waldur resource.
        """
        extra = None
        if project:
            project = self._get_project(project)
            extra = {"project_uuid": project["uuid"]}
        return self._get_resource(Endpoints.OpenStackTenant, name, extra)

    def _wait_for_resource(self, endpoint, uuid, interval, timeout):
        ready = self._is_resource_ready(endpoint, uuid)
        waited = 0
        while not ready:
            time.sleep(interval)
            ready = self._is_resource_ready(endpoint, uuid)
            waited += interval
            if waited >= timeout:
                error = (
                    'Resource "%s" with id "%s" has not changed state to stable.'
                    % (endpoint, uuid)
                )
                message = "%s. Seconds passed: %s" % (error, timeout)
                raise TimeoutError(message)

    def _wait_for_external_ip(self, uuid, interval, timeout):
        ready = self._instance_has_external_ip(uuid)
        waited = 0
        while not ready:
            time.sleep(interval)
            ready = self._instance_has_external_ip(uuid)
            waited += interval
            if waited >= timeout:
                error = 'Resource "%s" with id "%s" has not got external IP.' % uuid
                message = "%s. Seconds passed: %s" % (error, timeout)
                raise TimeoutError(message)

    def _instance_has_external_ip(self, uuid):
        resource = self._query_resource_by_uuid(Endpoints.OpenStackInstance, uuid)
        return len(resource["external_ips"]) > 0

    def list_tenants(self, filters=None):
        endpoint = self._build_url(Endpoints.OpenStackTenant)
        return self._query_resource_list(endpoint, filters)

    def list_networks(self, filters=None):
        endpoint = self._build_url(Endpoints.OpenStackNetwork)
        return self._query_resource_list(endpoint, filters)

    def list_marketplace_categories(self, filters=None):
        endpoint = self._build_url(Endpoints.MarketplaceCategories)
        return self._query_resource_list(endpoint, filters)

    def connect_subnet(self, uuid):
        return self._execute_resource_action(
            endpoint=Endpoints.OpenStackSubnet,
            uuid=uuid,
            action="connect",
        )

    def disconnect_subnet(self, uuid):
        return self._execute_resource_action(
            endpoint=Endpoints.OpenStackSubnet,
            uuid=uuid,
            action="disconnect",
        )

    def unlink_subnet(self, uuid):
        return self._execute_resource_action(
            endpoint=Endpoints.OpenStackSubnet,
            uuid=uuid,
            action="unlink",
        )

    def create_subnet(
        self,
        name,
        tenant,
        project,
        network_uuid,
        cidr,
        allocation_pools,
        enable_dhcp,
        dns_nameservers,
        disable_gateway,
        gateway_ip=None,
        wait=True,
        interval=10,
        timeout=600,
    ):
        tenant = self._get_tenant(tenant, project)
        payload = {
            "name": name,
            "tenant": tenant,
            "project": project,
            "network_uuid": network_uuid,
            "cidr": cidr,
            "dns_nameservers": dns_nameservers,
            "allocation_pools": allocation_pools,
            "enable_dhcp": enable_dhcp,
            "disable_gateway": disable_gateway,
        }

        if gateway_ip:
            if disable_gateway:
                raise ValidationError(
                    "Gateway IP cannot be set if disabling gateway is requested"
                )
            payload.update({"gateway_ip": gateway_ip})

        if not gateway_ip and not disable_gateway:
            raise ValidationError(
                "Either gateway IP must be set or it must be disabled"
            )

        action_url = "%s/%s/create_subnet" % (
            Endpoints.OpenStackNetwork,
            network_uuid,
        )
        resource = self._create_resource(action_url, payload)

        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackNetwork, resource["uuid"], interval, timeout
            )

        return resource

    def update_subnet(
        self,
        uuid,
        name,
        tenant=None,
        gateway_ip=None,
        disable_gateway=None,
        enable_dhcp=None,
        dns_nameservers=None,
        connect_subnet=None,
        disconnect_subnet=None,
        unlink_subnet=None,
    ):
        payload = {
            "name": name,
        }
        if tenant:
            payload.update({"tenant": tenant})
        if gateway_ip:
            if disable_gateway:
                raise ValidationError(
                    "Gateway IP cannot be set if disabling gateway is requested"
                )
            payload.update({"gateway_ip": gateway_ip})
        if not gateway_ip and not disable_gateway:
            raise ValidationError(
                "Either gateway IP must be set or it must be disabled"
            )
        if disable_gateway:
            payload.update({"disable_gateway": disable_gateway})
        if enable_dhcp:
            payload.update({"enable_dhcp": enable_dhcp})
        if dns_nameservers:
            payload.update({"dns_nameservers": dns_nameservers})
        if connect_subnet:
            if disconnect_subnet:
                raise ValidationError(
                    "connect_subnet and disconnect_subnet cannot both be True"
                )
            self.connect_subnet(uuid)
        if disconnect_subnet:
            if connect_subnet:
                raise ValidationError(
                    "connect_subnet and disconnect_subnet cannot both be True"
                )
            self.disconnect_subnet(uuid)

        if unlink_subnet:
            self.unlink_subnet(uuid)

        return self._update_resource(Endpoints.OpenStackSubnet, uuid, payload)

    def list_subnets(self, filters=None):
        endpoint = self._build_url(Endpoints.OpenStackSubnet)
        return self._query_resource_list(endpoint, filters)

    def list_tenant_subnets(self, tenant):
        query = {"tenant": tenant}
        return self._query_resource_list(Endpoints.OpenStackSubnet, query)

    def list_service_settings(self, filters=None):
        endpoint = self._build_url(Endpoints.Provider)
        return self._query_resource_list(endpoint, filters)

    def create_security_group(
        self,
        tenant,
        name,
        rules,
        project=None,
        description=None,
        tags=None,
        wait=True,
        interval=10,
        timeout=600,
    ):
        """
        Creates OpenStack security group via Waldur API from passed parameters.

        :param tenant: uuid or name of the tenant to use.
        :param name: name of the security group.
        :param rules: list of rules to add the security group.
        :param project: name of the Waldur project where OpenStack tenant is located.
        :param description: arbitrary text.
        :param tags: list of tags to add to the security group.
        :param wait: defines whether the client has to wait for security group provisioning.
        :param interval: interval of security group state polling in seconds.
        :param timeout: a maximum amount of time to wait for security group provisioning.
        :return: security group as a dictionary.
        """
        tenant = self._get_tenant(tenant, project)
        payload = {"name": name, "rules": rules}
        if description:
            payload.update({"description": description})
        if tags:
            payload.update({"tags": tags})

        action_url = "%s/%s/create_security_group" % (
            Endpoints.OpenStackTenant,
            tenant["uuid"],
        )
        resource = self._create_resource(action_url, payload)

        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackSecurityGroup, resource["uuid"], interval, timeout
            )

        return resource

    def get_subnet_by_uuid(self, uuid):
        subnet = None
        try:
            subnet = self._get_tenant_subnet_by_uuid(uuid=uuid)
        except ObjectDoesNotExist:
            pass

        return subnet

    def delete_subnet(self, uuid):
        return self._delete_resource(Endpoints.OpenStackSubnet, uuid)

    def update_security_group_description(self, security_group, description):
        payload = {
            "name": security_group["name"],
            "description": description,
        }
        uuid = security_group["uuid"]
        return self._update_resource(Endpoints.OpenStackSecurityGroup, uuid, payload)

    def update_security_group_rules(self, security_group, rules):
        return self._execute_resource_action(
            endpoint=Endpoints.OpenStackSecurityGroup,
            uuid=security_group["uuid"],
            action="set_rules",
            json=rules,
        )

    def get_security_group(self, tenant, name):
        tenant = self._get_tenant(tenant)
        security_group = None
        try:
            security_group = self._get_tenant_security_group(
                tenant_uuid=tenant["uuid"], name=name
            )
        except ObjectDoesNotExist:
            pass

        return security_group

    def list_security_group(self, tenant):
        tenant = self._get_tenant(tenant)
        return self._get_tenant_security_groups(tenant["uuid"])

    def delete_security_group(self, uuid):
        return self._delete_resource(Endpoints.OpenStackSecurityGroup, uuid)

    def _get_instance(self, instance):
        return self._get_resource(Endpoints.OpenStackInstance, instance)

    def assign_floating_ips(
        self, instance, floating_ips, wait=True, interval=20, timeout=600
    ):
        instance = self._get_instance(instance)
        payload: AssignFloatingIpPayload = {
            "floating_ips": [],
        }
        for ip in floating_ips:
            payload["floating_ips"].append(
                {
                    "url": self._get_floating_ip(ip["address"])["url"],
                    "subnet": self._get_subnet(ip["subnet"])["url"],
                }
            )

        endpoint = "%s/%s/update_floating_ips" % (
            Endpoints.OpenStackInstance,
            instance["uuid"],
        )
        response = self._create_resource(endpoint, payload, valid_state=202)

        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackInstance, instance["uuid"], interval, timeout
            )

        return response

    def _get_project_resource(self, endpoint, name, project=None):
        if is_uuid(name):
            return self._query_resource_by_uuid(endpoint, name)
        else:
            if project is None:
                raise ValidationError(
                    "You should specify project name if name is not UUID"
                )
            if is_uuid(project):
                query = {"project_uuid": project, "name_exact": name}
            else:
                query = {"project_name": project, "name_exact": name}
            return self._query_resource(endpoint, query)

    def get_instance(self, name, project=None):
        """
        Deprecated. Use get_instance_via_marketplace marketplace method"""
        return self._get_project_resource(Endpoints.OpenStackInstance, name, project)

    def get_marketplace_resource_scope(self, name, offering_type, project=None):
        """Get marketplace resource scope. Depending on the offering type scope type can be different.

        :param name: name of the scope.
        :param offering_type: marketplace offering type.
        :param project: project UUID or name.
        """

        if not is_uuid(name) and not project:
            raise ValidationError("You should specify project name if name is not UUID")

        endpoint = Endpoints.MarketplaceResources
        url = self._build_url(endpoint)
        params = {
            "offering_type": offering_type,
        }

        if is_uuid(name):
            params["scope"] = self._build_url(
                self.marketplaceScopeEndpoints[offering_type] + "/" + name
            )
        else:
            params["state"] = ["Creating", "OK", "Erred", "Updating", "Terminating"]
            params["name_exact"] = name

        if project:
            if is_uuid(project):
                params["project_uuid"] = project
            else:
                params["project_name"] = project

        result = self._get(url, valid_states=[200], params=params)

        if not result:
            message = "Result is empty. Endpoint: %s. Query: %s" % (endpoint, params)
            raise ObjectDoesNotExist(message)

        if len(result) > 1:
            message = "Ambiguous result. Endpoint: %s. Query: %s" % (url, params)
            raise MultipleObjectsReturned(message)

        scope = self._get(result[0]["scope"], valid_states=[200])
        if not scope:
            message = "Result is empty. Endpoint: %s. Query: %s" % (endpoint, params)
            raise ObjectDoesNotExist(message)

        return result[0], scope

    def get_marketplace_resource(self, resource_uuid):
        return self._get_resource(Endpoints.MarketplaceResources, resource_uuid)

    def get_marketplace_provider_resource(self, resource_uuid):
        return self._get_resource(Endpoints.MarketplaceProviderResources, resource_uuid)

    def filter_marketplace_resources(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceResources, filters)

    def filter_marketplace_provider_resources(self, filters=None):
        return self._query_resource_list(
            Endpoints.MarketplaceProviderResources, filters
        )

    def _list_marketplace_resources(
        self,
        endpoint: str,
        provider_uuid: Optional[str] = None,
        state: Optional[str] = None,
        offering_uuid: Optional[str] = None,
        fields: Optional[List[str]] = None,
        project_uuid: Optional[str] = None,
    ):
        params: ListMarketplaceResourcesPayload = {}
        if provider_uuid is not None:
            params["provider_uuid"] = provider_uuid
        if state is not None:
            params["state"] = state
        if offering_uuid is not None:
            params["offering_uuid"] = offering_uuid
        if project_uuid is not None:
            params["project_uuid"] = project_uuid
        if fields is not None:
            if not isinstance(fields, list):
                fields = [fields]
            params["field"] = fields

        return self._query_resource_list(endpoint, params)

    def list_marketplace_resources(
        self,
        provider_uuid: Optional[str] = None,
        state: Optional[str] = None,
        offering_uuid: Optional[str] = None,
        fields: Optional[List[str]] = None,
        project_uuid: Optional[str] = None,
    ):
        return self._list_marketplace_resources(
            Endpoints.MarketplaceResources,
            provider_uuid,
            state,
            offering_uuid,
            fields,
            project_uuid,
        )

    def list_marketplace_provider_resources(
        self,
        provider_uuid: Optional[str] = None,
        state: Optional[str] = None,
        offering_uuid: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ):
        return self._list_marketplace_resources(
            Endpoints.MarketplaceProviderResources,
            provider_uuid,
            state,
            offering_uuid,
            fields,
        )

    def count_marketplace_resources(self, **kwargs):
        url = self._build_url(Endpoints.MarketplaceResources)
        return self._get_count(url, **kwargs)

    def count_marketplace_provider_resources(self, **kwargs):
        url = self._build_url(Endpoints.MarketplaceProviderResources)
        return self._get_count(url, **kwargs)

    def marketplace_provider_resource_set_backend_id(
        self, resource_uuid: str, backend_id: str
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources,
            resource_uuid,
            action="set_backend_id",
        )
        payload = {"backend_id": backend_id}
        return self._post(url, valid_states=[200], json=payload)

    def marketplace_provider_resource_set_backend_metadata(
        self, resource_uuid: str, backend_metadata: typing.Dict[str, typing.Any]
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources,
            resource_uuid,
            action="set_backend_metadata",
        )
        payload = {"backend_metadata": backend_metadata}
        return self._post(url, valid_states=[200], json=payload)

    def marketplace_provider_resource_set_as_erred(
        self,
        resource_uuid,
        error_details: typing.Optional[typing.Dict[str, str]] = None,
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources,
            resource_uuid,
            action="set_as_erred",
        )
        return self._post(url, valid_states=[200], json=error_details)

    def marketplace_provider_resource_set_as_ok(
        self,
        resource_uuid,
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources,
            resource_uuid,
            action="set_as_ok",
        )
        return self._post(url, valid_states=[200])

    def marketplace_provider_resource_submit_report(
        self, resource_uuid: str, report: List[ResourceReportRecord]
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources,
            resource_uuid,
            action="submit_report",
        )
        payload = {"report": report}
        return self._post(url, valid_states=[200], json=payload)

    def marketplace_provider_resource_get_team(self, resource_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources, resource_uuid, action="team"
        )
        return self._get(url, valid_states=[200])

    def marketplace_provider_resource_get_plan_periods(self, resource_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources, resource_uuid, action="plan_periods"
        )
        return self._get(url, valid_states=[200])

    def marketplace_resource_get_plan_periods(self, resource_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceResources, resource_uuid, action="plan_periods"
        )
        return self._get(url, valid_states=[200])

    def marketplace_resource_update_options(
        self, resource_uuid: str, options: typing.Dict[str, typing.Any]
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceResources, resource_uuid, action="update_options"
        )
        payload = {"options": options}
        return self._post(url, valid_states=[200], json=payload)

    def marketplace_public_offering_get_plans(self, offering_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplacePublicOffering, offering_uuid, action="plans"
        )
        return self._get(url, valid_states=[200])

    def marketplace_public_offering_get_plan_details(
        self, offering_uuid: str, plan_uuid: str
    ):
        url = self._build_resource_url(
            Endpoints.MarketplacePublicOffering,
            offering_uuid,
            sub_endpoint="plans",
            uid2=plan_uuid,
        )
        return self._get(url, valid_states=[200])

    def update_marketplace_resource(self, resource_uuid: str, **kwargs):
        return self._patch_resource(
            Endpoints.MarketplaceResources, resource_uuid, kwargs
        )

    def update_marketplace_provider_resource(self, resource_uuid: str, **kwargs):
        return self._patch_resource(
            Endpoints.MarketplaceProviderResources, resource_uuid, kwargs
        )

    def get_instance_via_marketplace(self, name, project=None):
        """Get an openstack instance via marketplace.

        :param name: name of the instance.
        :param project: project UUID or name.
        """
        resource, instance = self.get_marketplace_resource_scope(
            name, ResourceTypes.OpenStackInstance, project
        )
        return instance

    def get_volume_via_marketplace(self, name, project=None):
        """Get an openstack volume via marketplace.

        :param name: name of the volume.
        :param project: project UUID or name.
        """
        resource, instance = self.get_marketplace_resource_scope(
            name, ResourceTypes.OpenStackVolume, project
        )
        return instance

    def stop_instance(self, uuid, wait=True, interval=10, timeout=600):
        """
        Stop OpenStack instance and wait until operation is completed.

        :param uuid: unique identifier of the instance
        :param wait: defines whether the client has to wait for operation completion.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for operation completion.
        """
        self._execute_resource_action(Endpoints.OpenStackInstance, uuid, "stop")
        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackInstance, uuid, interval, timeout
            )

    def update_instance_security_groups(
        self,
        instance_uuid,
        security_groups,
        wait=True,
        interval=10,
        timeout=600,
    ):
        """
        Update security groups for OpenStack instance and wait until operation is completed.

        :param instance_uuid: unique identifier of the instance
        :param security_groups: list of security group names
        :param wait: defines whether the client has to wait for operation completion.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for operation completion.
        """
        payload = []
        instance = self._get_instance(instance_uuid)
        tenant_uuid = instance["tenant_uuid"]
        for group in security_groups:
            security_group = self._get_tenant_security_group(tenant_uuid, group)
            payload.append({"url": security_group["url"]})

        self._execute_resource_action(
            endpoint=Endpoints.OpenStackInstance,
            uuid=instance_uuid,
            action="update_security_groups",
            json=dict(security_groups=payload),
        )
        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackInstance, instance_uuid, interval, timeout
            )

    def get_volume(self, name, project=None):
        return self._get_project_resource(Endpoints.OpenStackVolume, name, project)

    def _get_volume(self, name):
        return self._get_resource(Endpoints.OpenStackVolume, name)

    def update_volume(self, volume, description):
        payload = {
            "name": volume["name"],
            "description": description,
        }
        uuid = volume["uuid"]
        return self._update_resource(Endpoints.OpenStackVolume, uuid, payload)

    def detach_volume(self, uuid, wait=True, interval=10, timeout=600):
        """
        Detach OpenStack volume from instance and wait until operation is completed.

        :param uuid: unique identifier of the volume
        :param wait: defines whether the client has to wait for operation completion.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for operation completion.
        """
        self._execute_resource_action(Endpoints.OpenStackVolume, uuid, "detach")
        if wait:
            self._wait_for_resource(Endpoints.OpenStackVolume, uuid, interval, timeout)

    def attach_volume(
        self, volume, instance, device, wait=True, interval=10, timeout=600
    ):
        """
        Detach OpenStack volume from instance and wait until operation is completed.

        :param volume: unique identifier of the volume
        :param instance: unique identifier of the instance
        :param device: name of volume as instance device e.g. /dev/vdb
        :param wait: defines whether the client has to wait for operation completion.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for operation completion.
        """
        payload = dict(
            instance=self._build_resource_url(Endpoints.OpenStackInstance, instance),
            device=device,
        )
        self._execute_resource_action(
            Endpoints.OpenStackVolume, volume, "attach", json=payload
        )
        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackVolume, volume, interval, timeout
            )

    def get_snapshot(self, name):
        return self._get_resource(Endpoints.OpenStackSnapshot, name)

    def delete_snapshot(self, uuid):
        return self._delete_resource(Endpoints.OpenStackSnapshot, uuid)

    def create_snapshot(
        self,
        name,
        volume,
        kept_until=None,
        description=None,
        tags=None,
        wait=True,
        interval=10,
        timeout=600,
    ):
        """
        Creates OpenStack snapshot via Waldur API from passed parameters.

        :param name: name of the snapshot.
        :param volume: name or ID of the volume.
        :param kept_until: Guaranteed time of snapshot retention. If null - keep forever.
        :param description: arbitrary text.
        :param tags: list of tags to add to the snapshot.
        :param wait: defines whether the client has to wait for snapshot provisioning.
        :param interval: interval of snapshot state polling in seconds.
        :param timeout: a maximum amount of time to wait for snapshot provisioning.
        :return: snapshot as a dictionary.
        """
        volume = self._get_volume(volume)
        payload = {
            "name": name,
        }
        if description:
            payload.update({"description": description})
        if tags:
            payload.update({"tags": tags})
        if kept_until:
            payload.update({"kept_until": kept_until})

        action_url = "%s/%s/snapshot" % (Endpoints.OpenStackVolume, volume["uuid"])
        resource = self._create_resource(action_url, payload)

        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackSnapshot, resource["uuid"], interval, timeout
            )

        return resource

    def update_instance_ports(
        self, instance_uuid, subnet_set, wait=True, interval=10, timeout=600
    ):
        """
        Update internal ip for OpenStack instance and wait until operation is completed.

        :param instance_uuid: unique identifier of the instance
        :param subnet_set: list of subnet names
        :param wait: defines whether the client has to wait for operation completion.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for operation completion.
        """

        payload: UpdateInstancePortsPayload = {"ports": []}
        for subnet in subnet_set:
            subnet = self._get_subnet(subnet)
            payload["ports"].append({"subnet": subnet["url"]})

        self._execute_resource_action(
            endpoint=Endpoints.OpenStackInstance,
            uuid=instance_uuid,
            action="update_ports",
            json=payload,
        )
        if wait:
            self._wait_for_resource(
                Endpoints.OpenStackInstance, instance_uuid, interval, timeout
            )

    def _get_offering(self, offering, project=None):
        """
        Get marketplace offering.

        :param offering: the name or UUID of the offering.
        :param project: the name or UUID of the project. It is required if offering is not UUID.
        :return: marketplace offering.
        """
        if is_uuid(offering):
            return self._get_resource(Endpoints.MarketplacePublicOffering, offering)
        elif project:
            if is_uuid(project):
                project_uuid = project
            else:
                project = self._get_resource(Endpoints.Project, project)
                project_uuid = project["uuid"]

            return self._get_resource(
                Endpoints.MarketplacePublicOffering,
                offering,
                {"project_uuid": project_uuid, "state": ["Active", "Paused"]},
            )
        else:
            return

    def _get_plan(self, offering_identifier, plan_identifier):
        return self.marketplace_public_offering_get_plan_details(
            offering_identifier, plan_identifier
        )

    def create_marketplace_order(
        self, project, offering, plan=None, attributes=None, limits=None
    ):
        """
        Create order with one item in Waldur Marketplace.

        :param project: the name or UUID of the project
        :param offering: the name or UUID of the offering
        :param plan: the name or UUID of the plan.
        :param attributes: order item attributes.
        :param limits: order item limits.
        """
        project_uuid = self._get_project(project)["uuid"]
        offering_uuid = self._get_offering(offering, project)["uuid"]
        plan_uuid = plan and self._get_plan(offering_uuid, plan)["uuid"]
        return self.marketplace_resource_create_order(
            project_uuid, offering_uuid, plan_uuid, attributes, limits
        )

    def get_order(self, order_uuid):
        return self._get_resource(Endpoints.MarketplaceOrder, order_uuid)

    def list_orders(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceOrder, filters)

    def marketplace_order_approve_by_consumer(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="approve_by_consumer",
        )
        return self._post(url, valid_states=[200])

    def marketplace_order_approve_by_provider(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="approve_by_provider",
        )
        return self._post(url, valid_states=[200])

    def marketplace_order_reject_by_consumer(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="reject_by_consumer",
        )
        return self._post(url, valid_states=[200])

    def marketplace_order_reject_by_provider(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="reject_by_provider",
        )
        return self._post(url, valid_states=[200])

    def marketplace_order_cancel(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="cancel",
        )

        return self._post(url, valid_states=[202])

    def marketplace_order_set_state_executing(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="set_state_executing",
        )

        return self._post(url, valid_states=[200])

    def marketplace_order_set_state_done(self, order_uuid: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="set_state_done",
        )

        return self._post(url, valid_states=[200])

    def marketplace_order_set_state_erred(
        self,
        order_uuid: str,
        error_message: str = "",
        error_traceback: str = "",
    ):
        payload = {"error_message": error_message, "error_traceback": error_traceback}

        url = self._build_resource_url(
            Endpoints.MarketplaceOrder,
            order_uuid,
            action="set_state_erred",
        )

        return self._post(url, json=payload, valid_states=[200])

    def _get_resource_from_creation_order(
        self,
        order_uuid,
        resource_field="resource_uuid",
        interval=10,
        timeout=600,
    ):
        waited = 0
        while True:
            order = self.get_order(order_uuid)
            if order["state"] == "erred":
                raise InvalidStateError(order["error_message"])

            resource_uuid = order.get(resource_field)
            if resource_uuid:
                return resource_uuid
            time.sleep(interval)

            waited += interval
            if waited >= timeout:
                error = (
                    'Resource reference has not been found from order item "%s" '
                    % order_uuid
                )
                message = "%s. Seconds passed: %s" % (error, timeout)
                raise TimeoutError(message)

    def _create_scope_via_marketplace(
        self,
        offering,
        project,
        attributes,
        scope_endpoint,
        interval=10,
        timeout=600,
        wait=True,
        check_mode=False,
    ):
        """
        Create marketplace resource scope via marketplace.

        :param offering: the name or UUID of marketplace offering.
        :param project: the name or UUID of the project.
        :param attributes: order item attributes.
        :param scope_endpoint: scope endpoint.
        :param interval: interval of instance state polling in seconds.
        :param timeout: a maximum amount of time to wait for instance provisioning.
        :param wait: defines whether the client has to wait for instance provisioning.
        :param check_mode: True for check mode.
        :return: resource_uuid.
        """
        offering = self._get_offering(offering, project)

        if check_mode:
            return {
                "attributes": attributes,
                "project": project,
                "offering": offering["uuid"],
            }

        order = self.create_marketplace_order(
            project, offering["uuid"], attributes=attributes
        )
        order_uuid = order["uuid"]

        resource_uuid = self._get_resource_from_creation_order(order_uuid)

        if wait:
            self._wait_for_resource(scope_endpoint, resource_uuid, interval, timeout)

        return resource_uuid

    def create_resource_via_marketplace(
        self, project_uuid, offering_uuid, plan_uuid, attributes, limits
    ):
        order = self.create_marketplace_order(
            project_uuid, offering_uuid, plan_uuid, attributes, limits
        )
        order_uuid = order["uuid"]
        marketplace_resource_uuid = self._get_resource_from_creation_order(
            order_uuid, "marketplace_resource_uuid"
        )
        return {
            "create_order_uuid": order_uuid,
            "marketplace_resource_uuid": marketplace_resource_uuid,
        }

    def create_instance_via_marketplace(
        self,
        name,
        offering,
        project,
        networks,
        image,
        system_volume_size,
        description=None,
        flavor=None,
        flavor_min_cpu=None,
        flavor_min_ram=None,
        interval=10,
        timeout=600,
        wait=True,
        ssh_key=None,
        data_volume_size=None,
        security_groups=None,
        server_group=None,
        tags=None,
        user_data=None,
        check_mode=False,
        system_volume_type=None,
        data_volume_type=None,
    ):
        """
        Create OpenStack instance from passed parameters via marketplace.

        :param name: name of the instance.
        :param description: description of the instance.
        :param offering: the name or UUID of the offering
        :param project: uuid or name of the project to add the instance.
        :param networks: a list of networks to attach instance to.
        :param flavor: uuid or name of the flavor to use.
        :param flavor_min_cpu: min cpu count.
        :param flavor_min_ram: min ram size (MB).
        :param image: uuid or name of the image to use.
        :param system_volume_size: size of the system volume in GB.
        :param system_volume_type: UUID or name of system volume type.
        :param interval: interval of instance state polling in seconds.
        :param timeout: a maximum amount of time to wait for instance provisioning.
        :param wait: defines whether the client has to wait for instance provisioning.
        :param ssh_key: uuid or name of the ssh key to add to the instance.
        :param data_volume_size: size of the data volume in GB.
            No data volume is going to be created if empty.
        :param data_volume_type: UUID or name of data volume type.
        :param security_groups: list of security groups to add to the instance.
        :param server_group: A server group to add to the instance.
        :param tags: list of tags to add to the instance.
        :param user_data: additional data that will be added to the instance.
        :return: an instance as a dictionary.
        """
        offering = self._get_offering(offering, project)
        tenant_uuid = offering["scope_uuid"]

        # Collect attributes
        if flavor:
            flavor = self._get_flavor(flavor, tenant_uuid)
        else:
            flavor = self._get_flavor_from_params(flavor_min_cpu, flavor_min_ram)

        image = self._get_image(image, tenant_uuid)
        subnets, floating_ips = self._networks_to_payload(networks)

        attributes = {
            "name": name,
            "flavor": flavor["url"],
            "image": image["url"],
            "system_volume_size": system_volume_size * 1024,
            "ports": subnets,
            "floating_ips": floating_ips,
        }

        if security_groups:
            attributes["security_groups"] = []
            for group in security_groups:
                security_group = self._get_tenant_security_group(tenant_uuid, group)
                attributes["security_groups"].append({"url": security_group["url"]})

        if data_volume_size:
            attributes.update({"data_volume_size": data_volume_size * 1024})
        if user_data:
            attributes.update({"user_data": user_data})
        if ssh_key:
            ssh_key = self._get_resource(Endpoints.SshKey, ssh_key)
            attributes.update({"ssh_public_key": ssh_key["url"]})
        if description:
            attributes["description"] = description
        if tags:
            attributes.update({"tags": tags})
        if system_volume_type:
            volume_type = self._get_volume_type(system_volume_type, tenant_uuid)
            attributes.update({"system_volume_type": volume_type["url"]})
        if data_volume_type:
            volume_type = self._get_volume_type(data_volume_type, tenant_uuid)
            attributes.update({"data_volume_type": volume_type["url"]})
        if server_group:
            server_group = self._get_resource(
                Endpoints.OpenStackServerGroup, server_group
            )
            attributes.update({"server_group": server_group["url"]})

        resource_uuid = self._create_scope_via_marketplace(
            offering["uuid"],
            project,
            attributes,
            scope_endpoint=Endpoints.OpenStackInstance,
            interval=interval,
            timeout=timeout,
            wait=wait,
            check_mode=check_mode,
        )

        if wait and floating_ips:
            self._wait_for_external_ip(resource_uuid, interval, timeout)

        return resource_uuid

    def _delete_scope_via_marketplace(self, scope_uuid, offering_type, options=None):
        resource, scope = self.get_marketplace_resource_scope(scope_uuid, offering_type)
        return self.marketplace_resource_terminate_order(resource["uuid"], options)

    def delete_instance_via_marketplace(self, instance_uuid, **kwargs):
        """
        Delete OpenStack instance via marketplace.

        :param instance_uuid: instance UUID.
        """
        return self._delete_scope_via_marketplace(
            instance_uuid, ResourceTypes.OpenStackInstance, options=kwargs
        )

    def create_volume_via_marketplace(
        self,
        name,
        project,
        offering,
        size,
        volume_type=None,
        description=None,
        tags=None,
        wait=True,
        interval=10,
        timeout=600,
    ):
        """
        Create OpenStack volume from passed parameters via marketplace.

        :param name: name of the volume.
        :param project: uuid or name of the project to add the volume to.
        :param offering: the name or UUID of the offering
        :param size: size of the volume in GBs.
        :param volume_type: uuid or name of volume type.
        :param description: arbitrary text.
        :param tags: list of tags to add to the volume.
        :param wait: defines whether the client has to wait for volume provisioning.
        :param interval: interval of volume state polling in seconds.
        :param timeout: a maximum amount of time to wait for volume provisioning.
        :return: volume as a dictionary.
        """

        offering = self._get_offering(offering, project)
        tenant_uuid = offering["scope_uuid"]

        # Collect attributes
        attributes = {
            "name": name,
            "size": size * 1024,
        }
        if description:
            attributes.update({"description": description})
        if tags:
            attributes.update({"tags": tags})
        if volume_type:
            volume_type = self._get_volume_type(volume_type, tenant_uuid)
            attributes.update({"type": volume_type["url"]})

        return self._create_scope_via_marketplace(
            offering["uuid"],
            project,
            attributes,
            scope_endpoint=Endpoints.OpenStackVolume,
            interval=interval,
            timeout=timeout,
            wait=wait,
        )

    def delete_volume_via_marketplace(self, volume_uuid):
        """
        Delete OpenStack volume via marketplace.

        :param volume_uuid: volume UUID.
        """
        return self._delete_scope_via_marketplace(volume_uuid, "OpenStack.Volume")

    def create_offering(self, params, check_mode=False):
        """
        Create an offering with specified parameters

        :param params: dict with parameters
        :param check_mode: True for check mode.
        :return: new offering information
        """
        category_url = self._get_resource(
            Endpoints.MarketplaceCategories, params["category"]
        )["url"]
        params["category"] = category_url
        if params["customer"]:
            customer_url = self._get_resource(Endpoints.Customers, params["customer"])[
                "url"
            ]
            params["customer"] = customer_url

        if check_mode:
            return params, False

        else:
            resource = self._create_resource(
                Endpoints.MarketplaceProviderOffering, payload=params
            )

            return resource, True

    def get_customer(self, identifier, filters=None):
        return self._get_resource(Endpoints.Customers, identifier, filters)

    def list_customers(self, filters=None):
        return self._query_resource_list(Endpoints.Customers, filters)

    def count_customers(self):
        url = self._build_url(Endpoints.Customers)
        return self._get_count(url)

    def create_customer(
        self,
        name,
        email="",
        address="",
        registration_code="",
        backend_id="",
        abbreviation="",
        bank_account="",
        bank_name="",
        contact_details="",
        country="",
        display_name="",
        domain="",
        homepage="",
        native_name="",
        latitude=None,
        longitude=None,
        phone_number="",
        postal="",
        vat_code="",
    ):
        payload = {
            "abbreviation": abbreviation,
            "address": address,
            "bank_account": bank_account,
            "bank_name": bank_name,
            "contact_details": contact_details,
            "country": country,
            "display_name": display_name,
            "domain": domain,
            "email": email,
            "homepage": homepage,
            "name": name,
            "native_name": native_name,
            "registration_code": registration_code,
            "backend_id": backend_id,
            "latitude": latitude,
            "longitude": longitude,
            "phone_number": phone_number,
            "postal": postal,
            "vat_code": vat_code,
        }
        return self._create_resource(Endpoints.Customers, payload=payload)

    def delete_offering_user(self, offering_user):
        """
        Delete a offering user by UUID or URL

        :param offering_user: offering user's UUID or URL
        """
        if is_uuid(offering_user):
            return self._delete_resource(
                Endpoints.MarketplaceOfferingUsers, offering_user
            )
        return self._delete_resource_by_url(offering_user)

    def delete_customer(self, customer):
        """
        Delete a customer by UUID or URL

        :param customer: customer's UUID or URL
        :return: deleted customer information
        """
        if is_uuid(customer):
            return self._delete_resource(Endpoints.Customers, customer)
        return self._delete_resource_by_url(customer)

    def list_projects(self, filters=None):
        return self._query_resource_list(Endpoints.Project, filters)

    def count_projects(self):
        url = self._build_url(Endpoints.Project)
        return self._get_count(url)

    def _serialize_project(
        self,
        type_uuid=None,
        **kwargs,
    ):
        type_url = type_uuid and self._build_resource_url(
            Endpoints.ProjectTypes, type_uuid
        )
        return {
            **kwargs,
            "type": type_url,
        }

    def create_project(self, customer_uuid, name, **kwargs):
        payload = self._serialize_project(name=name, **kwargs)
        payload["customer"] = self._build_resource_url(
            Endpoints.Customers, customer_uuid
        )

        return self._create_resource(Endpoints.Project, payload=payload)

    def update_project(self, project_uuid, **kwargs):
        payload = self._serialize_project(**kwargs)
        return self._patch_resource(Endpoints.Project, project_uuid, payload=payload)

    def delete_project(self, project):
        """
        Delete a project by UUID or URL

        :param project: project's UUID or URL
        :return: deleted project information
        """
        if is_uuid(project):
            return self._delete_resource(Endpoints.Project, project)
        return self._delete_resource_by_url(project)

    def list_marketplace_provider_offerings(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceProviderOffering, filters)

    def list_marketplace_public_offerings(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplacePublicOffering, filters)

    def get_marketplace_provider_offering(self, offering_uuid):
        return self._query_resource_by_uuid(
            Endpoints.MarketplaceProviderOffering, offering_uuid
        )

    def get_marketplace_public_offering(self, offering_uuid):
        return self._query_resource_by_uuid(
            Endpoints.MarketplacePublicOffering, offering_uuid
        )

    def marketplace_resource_create_order(
        self,
        project_uuid,
        offering_uuid,
        plan_uuid=None,
        attributes=None,
        limits=None,
        callback_url=None,
    ):
        attributes = attributes or {}
        limits = limits or {}
        payload = {
            "project": self._build_resource_url(Endpoints.Project, project_uuid),
            "offering": self._build_resource_url(
                Endpoints.MarketplacePublicOffering, offering_uuid
            ),
            "attributes": attributes,
            "limits": limits,
            # TODO: replace with checkbox data from frontend
            "accepting_terms_of_service": True,
        }

        if plan_uuid:
            payload["plan"] = self._build_resource_url(
                Endpoints.MarketplacePublicOffering,
                offering_uuid,
                sub_endpoint="plans",
                uid2=plan_uuid,
            )

        if callback_url:
            payload["callback_url"] = callback_url

        return self._create_resource(Endpoints.MarketplaceOrder, payload=payload)

    def marketplace_resource_update_limits_order(
        self, resource_uuid, limits, callback_url=None
    ):
        payload = {"limits": limits}
        if callback_url:
            payload["callback_url"] = callback_url
        url = self._build_resource_url(
            Endpoints.MarketplaceResources, resource_uuid, action="update_limits"
        )
        return self._post(url, valid_states=[200], json=payload)["order_uuid"]

    def marketplace_resource_terminate_order(
        self, resource_uuid, options=None, callback_url=None
    ):
        if options:
            options = {"attributes": options}
        if callback_url:
            if not options:
                options = {}
            options["callback_url"] = callback_url
        url = self._build_resource_url(
            Endpoints.MarketplaceResources, resource_uuid, action="terminate"
        )
        return self._post(url, valid_states=[200], json=options)["order_uuid"]

    def marketplace_provider_resource_terminate_order(
        self, resource_uuid, options=None, callback_url=None
    ):
        if options:
            options = {"attributes": options}
        if callback_url:
            if not options:
                options = {}
            options["callback_url"] = callback_url
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderResources, resource_uuid, action="terminate"
        )
        return self._post(url, valid_states=[200], json=options)["order_uuid"]

    def get_invoice_for_customer(
        self,
        customer_uuid: str,
        year: int,
        month: int,
        state: Optional[InvoiceState] = None,
    ):
        query_params = {"customer_uuid": customer_uuid, "year": year, "month": month}
        if state is not None:
            query_params["state"] = state.value
        return self._query_resource(
            Endpoints.Invoice,
            query_params,
        )

    def invoice_set_backend_id(self, invoice_uuid: str, backend_id: str):
        url = self._build_resource_url(
            Endpoints.Invoice,
            invoice_uuid,
            action="set_backend_id",
        )
        payload = {"backend_id": backend_id}
        return self._post(url, valid_states=[200], json=payload)

    def invoice_set_payment_url(self, invoice_uuid: str, payment_url: str):
        url = self._build_resource_url(
            Endpoints.Invoice,
            invoice_uuid,
            action="set_payment_url",
        )
        payload = {"payment_url": payment_url}
        return self._post(url, valid_states=[200], json=payload)

    def invoice_set_reference_number(self, invoice_uuid: str, reference_number: str):
        url = self._build_resource_url(
            Endpoints.Invoice,
            invoice_uuid,
            action="set_reference_number",
        )
        payload = {"reference_number": reference_number}
        return self._post(url, valid_states=[200], json=payload)

    def invoice_set_state_paid(self, invoice_uuid: str):
        url = self._build_resource_url(Endpoints.Invoice, invoice_uuid, "paid")
        return self._post(url, valid_states=[200])

    def list_invoice_items(self, filters=None):
        return self._query_resource_list(Endpoints.InvoiceItems, filters)

    def list_payment_profiles(self, filters=None):
        if "payment_type" in filters:
            filters["payment_type"] = filters["payment_type"].value
        return self._query_resource_list(Endpoints.PaymentProfiles, filters)

    def list_component_usages(self, resource_uuid, date_after=None, date_before=None):
        return self._query_resource_list(
            Endpoints.MarketplaceComponentUsage,
            {
                "resource_uuid": resource_uuid,
                "date_after": date_after,
                "date_before": date_before,
            },
        )

    def create_component_usages(
        self,
        plan_period_uuid: Optional[str] = None,
        usages: List[ComponentUsage] = [],
        resource_uuid: Optional[str] = None,
    ):
        url = self._build_url(f"{Endpoints.MarketplaceComponentUsage}/set_usage/")
        payload: CreateComponentUsagePayload = {
            "usages": usages,
        }

        if plan_period_uuid is not None:
            payload.update(
                {
                    "plan_period": plan_period_uuid,
                }
            )
        else:
            if resource_uuid is not None:
                payload.update(
                    {
                        "resource": resource_uuid,
                    }
                )
            else:
                raise ValidationError(
                    "Neither plan_period_uuid nor resource_uuid provided"
                )

        return self._post(url, valid_states=[201], json=payload)

    def create_component_user_usage(
        self, component_usage_uuid, usage, username, offering_user_uuid=None
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceComponentUsage, component_usage_uuid, "set_user_usage"
        )
        payload = {"usage": usage, "username": username}
        if offering_user_uuid is not None and is_uuid(offering_user_uuid):
            offering_user_url = self._build_resource_url(
                Endpoints.MarketplaceOfferingUsers, offering_user_uuid
            )
            payload["user"] = offering_user_url
        self._post(url, valid_states=[201], json=payload)

    def get_remote_eduteams_user(self, cuid):
        return self._create_resource(
            Endpoints.RemoteEduteams,
            {
                "cuid": cuid,
            },
            valid_state=200,
        )

    def create_project_permission(
        self, project_uuid, user_uuid, role_uuid, expiration_time=None
    ):
        return self._post(
            self._build_url(f"projects/{project_uuid}/add_user/"),
            valid_states=[201],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def get_project_permissions(self, project_uuid, user_uuid=None, role_uuid=None):
        query_params = {}
        if role_uuid:
            query_params["role"] = role_uuid
        if user_uuid:
            query_params["user"] = user_uuid

        return self._query_resource_list(
            f"projects/{project_uuid}/list_users/", query_params
        )

    def update_project_permission(
        self, project_uuid, user_uuid, role_uuid, expiration_time
    ):
        return self._post(
            self._build_url(f"projects/{project_uuid}/update_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def remove_project_permission(self, project_uuid, user_uuid, role_uuid):
        return self._post(
            self._build_url(f"projects/{project_uuid}/delete_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
            },
        )

    def create_customer_permission(
        self, customer_uuid, user_uuid, role_uuid, expiration_time=None
    ):
        return self._post(
            self._build_url(f"customers/{customer_uuid}/add_user/"),
            valid_states=[201],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def get_customer_permissions(self, customer_uuid, user_uuid=None, role_uuid=None):
        query_params = {}
        if role_uuid:
            query_params["role"] = role_uuid
        if user_uuid:
            query_params["user"] = user_uuid

        return self._query_resource_list(
            f"customers/{customer_uuid}/list_users/", query_params
        )

    def update_customer_permission(
        self, customer_uuid, user_uuid, role_uuid, expiration_time
    ):
        return self._post(
            self._build_url(f"customers/{customer_uuid}/update_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def remove_customer_permission(self, customer_uuid, user_uuid, role_uuid):
        return self._post(
            self._build_url(f"customers/{customer_uuid}/delete_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
            },
        )

    def create_offering_permission(
        self, offering_uuid, user_uuid, role_uuid, expiration_time=None
    ):
        return self._post(
            self._build_url(f"offerings/{offering_uuid}/add_user/"),
            valid_states=[201],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def get_offering_permissions(self, offering_uuid, user_uuid=None, role_uuid=None):
        query_params = {}
        if role_uuid:
            query_params["role"] = role_uuid
        if user_uuid:
            query_params["user"] = user_uuid

        return self._query_resource_list(
            f"offerings/{offering_uuid}/list_users/", query_params
        )

    def update_offering_permission(
        self, offering_uuid, user_uuid, role_uuid, expiration_time
    ):
        return self._post(
            self._build_url(f"offerings/{offering_uuid}/update_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
                "expiration_time": expiration_time,
            },
        )

    def remove_offering_permission(self, offering_uuid, user_uuid, role_uuid):
        return self._post(
            self._build_url(f"offerings/{offering_uuid}/delete_user/"),
            valid_states=[200],
            json={
                "user": user_uuid,
                "role": role_uuid,
            },
        )

    def create_remote_offering_user(
        self, offering: str, user: str, username: Optional[str] = None
    ):
        if is_uuid(offering):
            offering = self._build_resource_url(
                Endpoints.MarketplaceProviderOffering, offering
            )

        if is_uuid(user):
            user = self._build_resource_url(Endpoints.Users, user)

        payload = {
            "offering": offering,
            "user": user,
        }

        if username is not None:
            payload["username"] = username

        return self._create_resource(Endpoints.MarketplaceOfferingUsers, payload)

    def set_offerings_username(
        self, service_provider_uuid: str, user_uuid: str, username: str
    ):
        endpoint = self._build_resource_url(
            Endpoints.MarketplaceServiceProviders,
            service_provider_uuid,
            "set_offerings_username",
        )
        payload = {
            "user_uuid": user_uuid,
            "username": username,
        }
        return self._post(endpoint, valid_states=[201], json=payload)

    def list_remote_offering_users(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceOfferingUsers, filters)

    def list_service_providers(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceServiceProviders, filters)

    def list_service_provider_users(self, service_provider_uuid):
        endpoint = self._build_resource_url(
            Endpoints.MarketplaceServiceProviders, service_provider_uuid, "users"
        )
        return self._query_resource_list(endpoint, None)

    def list_service_provider_projects(self, service_provider_uuid):
        endpoint = self._build_resource_url(
            Endpoints.MarketplaceServiceProviders, service_provider_uuid, "projects"
        )
        return self._query_resource_list(endpoint, None)

    def list_service_provider_project_permissions(self, service_provider_uuid):
        endpoint = self._build_resource_url(
            Endpoints.MarketplaceServiceProviders,
            service_provider_uuid,
            "project_permissions",
        )
        return self._query_resource_list(endpoint, None)

    def list_service_provider_ssh_keys(self, service_provider_uuid):
        endpoint = self._build_resource_url(
            Endpoints.MarketplaceServiceProviders, service_provider_uuid, "keys"
        )
        return self._query_resource_list(endpoint, None)

    def get_marketplace_stats(self, endpoint):
        endpoint = self._build_url(Endpoints.MarketplaceStats, endpoint)
        return self._make_request("get", endpoint, valid_states=[200])

    def get_slurm_allocation(self, uuid: str):
        if not is_uuid(uuid):
            raise ValidationError(
                "The UUID of SLURM allocation has unexpected format: %s" % uuid
            )
        return self._get_resource(Endpoints.SlurmAllocations, uuid)

    def list_slurm_allocations(self, filters=None):
        return self._query_resource_list(Endpoints.SlurmAllocations, filters)

    def set_slurm_allocation_state(
        self, marketplace_resource_uuid: str, state: SlurmAllocationState
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceSlurmRemote,
            marketplace_resource_uuid,
            "set_state",
        )
        payload = {"state": state.value}
        self._post(url, valid_states=[200], json=payload)

    def set_slurm_allocation_backend_id(
        self, marketplace_resource_uuid: str, backend_id: str
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceSlurmRemote,
            marketplace_resource_uuid,
            "set_backend_id",
        )
        payload = {"backend_id": backend_id}
        self._post(url, valid_states=[200], json=payload)

    def list_slurm_associations(self, filters=None):
        return self._query_resource_list(Endpoints.SlurmAssociations, filters)

    def create_slurm_association(self, marketplace_resource_uuid: str, username: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceSlurmRemote,
            marketplace_resource_uuid,
            "create_association",
        )
        payload = {"username": username}
        return self._post(url, valid_states=[200, 201], json=payload)

    def delete_slurm_association(self, marketplace_resource_uuid: str, username: str):
        url = self._build_resource_url(
            Endpoints.MarketplaceSlurmRemote,
            marketplace_resource_uuid,
            "delete_association",
        )
        payload = {"username": username}
        return self._post(url, valid_states=[200], json=payload)

    def set_slurm_allocation_limits(
        self,
        marketplace_resource_uuid: str,
        limits: typing.Dict[str, int],
    ):
        if not is_uuid(marketplace_resource_uuid):
            raise ValidationError(
                "The UUID of marketplace resource has unexpected format: %s"
                % marketplace_resource_uuid
            )
        url = self._build_resource_url(
            Endpoints.MarketplaceSlurmRemote,
            marketplace_resource_uuid,
            "set_limits",
        )
        return self._post(url, valid_states=[200], json=limits)

    def list_slurm_allocation_user_usage(self, filters=None):
        return self._query_resource_list(Endpoints.SlurmAllocationUserUsages, filters)

    def create_offering_component(
        self, offering_uuid: str, component: OfferingComponent
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderOffering,
            offering_uuid,
            "create_offering_component",
        )
        # Drop all keys with None or empty value
        component_json = {k: v for k, v in component.items() if v and k != "uuid"}
        return self._post(url, valid_states=[201], json=component_json)

    def update_offering_component(
        self, offering_uuid: str, component: OfferingComponent
    ):
        url = self._build_resource_url(
            Endpoints.MarketplaceProviderOffering,
            offering_uuid,
            "update_offering_component",
        )
        component_json = {k: v for k, v in component.items() if v}
        return self._post(url, valid_states=[200], json=component_json)

    def create_support_issue(
        self, summary, issue_type, caller_url, remote_id, **kwargs
    ):
        payload = {
            "summary": summary,
            "type": issue_type,
            "caller": caller_url,
            "remote_id": remote_id,
        }
        payload.update(kwargs)
        return self._create_resource(Endpoints.SupportIssues, payload=payload)

    def list_support_issues(self, filters=None):
        return self._query_resource_list(Endpoints.SupportIssues, filters)

    def list_support_comments(self, filters=None):
        return self._query_resource_list(Endpoints.SupportComments, filters)

    def create_support_comments(self, issue_uuid, description, remote_id, **kwargs):
        payload = {
            "description": description,
            "remote_id": remote_id,
        }
        payload.update(kwargs)
        return self._create_resource(
            Endpoints.SupportIssues + f"/{issue_uuid}/comment/", payload=payload
        )

    def list_robot_account(self, filters=None):
        return self._query_resource_list(Endpoints.MarketplaceRobotAccount, filters)

    def create_robot_account(self, resource, type, users=[], username="", keys=[]):
        params = {
            "resource": resource,
            "type": type,
            "users": users,
            "username": username,
            "keys": keys,
        }
        if is_uuid(resource):
            params["resource"] = self._build_url(
                Endpoints.MarketplaceResources + "/" + resource
            )
        if users:
            for idx, user in enumerate(users):
                if is_uuid(user):
                    params["users"][idx] = self._build_url(Endpoints.Users + "/" + user)
        return self._create_resource(
            Endpoints.MarketplaceRobotAccount,
            payload=params,
        )

    def update_robot_account(self, account_uuid, payload):
        return self._patch_resource(
            Endpoints.MarketplaceRobotAccount,
            account_uuid,
            payload,
        )

    def delete_robot_account(self, account_uuid):
        return self._delete_resource(
            Endpoints.MarketplaceRobotAccount,
            account_uuid,
        )

    def create_event_subscription(
        self,
        observable_objects: typing.List[typing.Dict[str, typing.Any]],
        description=None,
    ):
        payload = {"observable_objects": observable_objects}
        if description is not None:
            payload["description"] = description
        return self._create_resource(
            Endpoints.EventSubscriptions, payload, valid_state=201
        )

    def list_event_subscriptions(self, filters=None):
        return self._query_resource_list(Endpoints.EventSubscriptions, filters)

    def delete_event_subscription(self, event_subscription_uuid: str):
        return self._delete_resource(
            Endpoints.EventSubscriptions, event_subscription_uuid
        )


def waldur_full_argument_spec(**kwargs):
    spec = dict(
        api_url=dict(required=True, type="str"),
        access_token=dict(required=True, type="str", no_log=True),
        wait=dict(default=True, type="bool"),
        timeout=dict(default=600, type="int"),
        interval=dict(default=20, type="int"),
    )
    spec.update(kwargs)
    return spec


def waldur_resource_argument_spec(**kwargs):
    spec = dict(
        name=dict(required=True, type="str"),
        description=dict(type="str", default=""),
        state=dict(default="present", choices=["absent", "present"]),
        tags=dict(type="list", default=None),
    )
    spec.update(waldur_full_argument_spec(**kwargs))
    return spec


def waldur_client_from_module(module):
    return WaldurClient(module.params["api_url"], module.params["access_token"])
