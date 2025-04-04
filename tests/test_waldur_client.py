import json
import unittest
import uuid
from urllib.parse import parse_qs, urlencode, urlparse

import responses

from waldur_client import WaldurClient, WaldurClientException


class BaseWaldurClientTest(unittest.TestCase):
    def setUp(self):
        self.api_url = "http://example.com:8000/api"
        self.access_token = "token"
        self.client = WaldurClient(self.api_url, self.access_token)
        self.tenant = {"name": "tenant", "uuid": str(uuid.uuid4())}
        self.params = {}

    def _get_url(self, endpoint, params=None):
        url = "%(url)s/%(endpoint)s/"
        url = url % {
            "url": self.api_url,
            "endpoint": endpoint,
        }
        return "%s?%s" % (url, urlencode(params)) if params else url

    def _get_resource_url(self, endpoint, uuid):
        return "%s%s" % (self._get_url(endpoint), uuid)

    def _get_subresource_url(self, endpoint, uuid, action=None):
        url = self._get_resource_url(endpoint, uuid)
        return "%s/%s/" % (url, action) if action else url

    def _get_object(self, name):
        return {
            "url": "url_%s" % name,
            "uuid": "uuid_%s" % name,
            "name": self.params[name] if name in self.params else name,
        }


class SubnetTest(BaseWaldurClientTest):
    subnet = {
        "access_token": "token",
        "api_url": "api",
        "uuid": "df3ee5cac5874dffa1aad86bc1919d8d",
        "name": "subnet",
        "tenant": "tenant",
        "project": "59e46d029a79473779915a22",
        "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
        "gateway_ip": "192.168.42.1",
        "disable_gateway": False,
        "state": "present",
        "wait": True,
        "interval": 10,
        "timeout": 600,
        "connect_subnet": False,
        "disconnect_subnet": False,
    }

    @responses.activate
    def update_subnet(self, **kwargs):
        responses.add(
            responses.GET, self._get_url("openstack-subnets"), json=[self.subnet]
        )
        post_url = "%s/" % (
            self._get_subresource_url("openstack-subnets", self.subnet["uuid"])
        )
        responses.add(responses.PUT, post_url, json=self.subnet, status=200)

        instance_url = "%s/openstack-subnets/%s/" % (
            self.api_url,
            self.subnet["uuid"],
        )
        responses.add(responses.GET, instance_url, json=self.subnet, status=200)

        client = WaldurClient(self.api_url, self.access_token)
        response = client.update_subnet(
            uuid=self.subnet["uuid"],
            name=self.subnet["name"],
            tenant=self.tenant["uuid"],
            disable_gateway=self.subnet["disable_gateway"],
            gateway_ip=self.subnet.get("gateway_ip"),  # optional value
            **kwargs,
        )
        return response

    @responses.activate
    def test_waldur_client_raises_error_on_invalid_action_config(self):
        del self.subnet["gateway_ip"]

        self.assertRaises(WaldurClientException, self.update_subnet)

    @responses.activate
    def test_correct_body_sent(self):
        self.subnet = {
            "access_token": "token",
            "api_url": "api",
            "uuid": "df3ee5cac5874dffa1aad86bc1919d8d",
            "name": "subnet",
            "tenant": "tenant",
            "project": "59e46d029a79473779915a22",
            "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
            "gateway_ip": "192.168.42.1",
            "disable_gateway": False,
            "state": "present",
            "wait": True,
            "interval": 10,
            "timeout": 600,
            "connect_subnet": False,
            "disconnect_subnet": False,
        }
        response = self.update_subnet()
        self.assertEqual(
            response,
            {
                "access_token": "token",
                "api_url": "api",
                "uuid": "df3ee5cac5874dffa1aad86bc1919d8d",
                "name": "subnet",
                "tenant": "tenant",
                "project": "59e46d029a79473779915a22",
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
                "gateway_ip": "192.168.42.1",
                "disable_gateway": False,
                "state": "present",
                "wait": True,
                "interval": 10,
                "timeout": 600,
                "connect_subnet": False,
                "disconnect_subnet": False,
            },
        )


class SubnetConnectTest(BaseWaldurClientTest):
    def setUp(self):
        super(SubnetConnectTest, self).setUp()
        self.expected_url = (
            "http://example.com:8000/api/openstack-subnets/"
            "df3ee5cac5874dffa1aad86bc1919d8d/connect/"
        )

    @responses.activate
    def valid_url_used_for_action(self):
        responses.add(
            responses.POST,
            self.expected_url,
            status=202,
            json={"is_connected": True},
        )
        self.client.connect_subnet("df3ee5cac5874dffa1aad86bc1919d8d")


class InstanceCreateBaseTest(BaseWaldurClientTest):
    def setUp(self):
        super(InstanceCreateBaseTest, self).setUp()

        self.params = {
            "name": "instance",
            "project": "project",
            "networks": [
                {
                    "subnet": "subnet",
                    "floating_ip": "auto",
                }
            ],
            "security_groups": ["web"],
            "flavor": "flavor",
            "image": "image",
            "ssh_key": "ssh_key",
            "wait": True,
            "timeout": 600,
            "interval": 0.1,
            "user_data": "user_data",
            "system_volume_size": 10,
            "data_volume_size": 5,
        }

        self.flavor = {
            "url": "url_flavor",
            "uuid": "uuid",
            "name": "g1.small1",
            "settings": "url_settings",
            "cores": 1,
            "ram": 512,
            "disk": 10240,
        }

        self.instance = {
            "uuid": "uuid",
            "name": self.params["name"],
            "url": "url_instance",
            "state": "OK",
            "external_ips": ["142.124.1.50"],
        }

        post_url = "%s/openstack-instances/" % self.api_url
        mapping = {
            "project": "projects",
            "image": "openstack-images",
            "subnet": "openstack-subnets",
            "security_groups": "openstack-security-groups",
            "ssh_key": "keys",
        }
        for name in mapping:
            obj = self._get_object(name)
            responses.add(responses.GET, self._get_url(mapping[name]), json=[obj])

        security_group = self._get_object("security_group")
        responses.add(
            responses.GET,
            self._get_url("openstack-security-groups"),
            json=[security_group],
        )
        responses.add(responses.POST, post_url, json=self.instance, status=201)
        status_url = self._get_url("openstack-instances")
        responses.add(responses.GET, status_url, json=[self.instance])

        self.instance_url = "%s/openstack-instances/%s/" % (
            self.api_url,
            self.instance["uuid"],
        )
        responses.add(responses.GET, self.instance_url, json=self.instance)

        url = self._get_url(
            "openstack-flavors",
            {"tenant_uuid": "tenant_uuid", "name_exact": "flavor"},
        )
        responses.add(method="GET", url=url, json=[self.flavor])


class InstanceCreateViaMarketplaceTest(InstanceCreateBaseTest):
    def setUp(self):
        super(InstanceCreateViaMarketplaceTest, self).setUp()

        self.params["offering"] = "offering"

        offering = self._get_object("offering")
        offering["scope_uuid"] = "tenant_uuid"
        offering["type"] = "OpenStack.Instance"
        responses.add(
            responses.GET,
            self._get_url("marketplace-public-offerings"),
            json=[offering],
        )

        self.order = {
            "uuid": "9ae5e13294884628aaf984a82214f7c4",
            "state": "executing",
            "resource_uuid": self.instance["uuid"],
        }

        url = self._get_url("marketplace-orders")
        responses.add(responses.POST, url, json=self.order, status=201)

        url = self._get_url("marketplace-orders/%s" % self.order["uuid"])
        responses.add(responses.GET, url, json=self.order, status=200)

        url = self._get_url("marketplace-orders/order_uuid/approve_by_consumer")
        responses.add(responses.POST, url, json=self.order, status=200)

    @responses.activate
    def test_valid_body_is_sent(self):
        actual = self.create_instance()
        self.assertDictEqual(
            actual,
            {
                "project": self._get_url("projects/uuid_project"),
                "accepting_terms_of_service": True,
                "attributes": {
                    "name": "instance",
                    "image": "url_image",
                    "data_volume_size": 5120,
                    "user_data": "user_data",
                    "floating_ips": [{"subnet": "url_subnet"}],
                    "ports": [{"subnet": "url_subnet"}],
                    "ssh_public_key": "url_ssh_key",
                    "system_volume_size": 10240,
                    "flavor": "url_flavor",
                    "security_groups": [{"url": "url_security_groups"}],
                },
                "offering": self._get_url("marketplace-public-offerings/uuid_offering"),
                "limits": {},
            },
        )

    @responses.activate
    def test_flavors_are_filtered_by_ram_and_cpu(self):
        url = self._get_url(
            "openstack-flavors",
            {"ram__gte": 2000, "cores__gte": 2, "o": "cores,ram,disk"},
        )
        responses.add(
            method="GET",
            url=url,
            json=[self.flavor, self.flavor, self.flavor],
        )

        self.params.pop("flavor")
        self.params["flavor_min_cpu"] = 2
        self.params["flavor_min_ram"] = 2000

        actual = self.create_instance()
        self.assertEqual(actual["attributes"]["flavor"], self.flavor["url"])

    @responses.activate
    def test_if_networks_do_no_have_a_subnet_error_is_raised(self):
        del self.params["networks"][0]["subnet"]

        self.assertRaises(WaldurClientException, self.create_instance)

    @responses.activate
    def test_wait_for_floating_ip(self):
        self.create_instance()
        self.assertEqual(
            2,
            len(
                [
                    call
                    for call in responses.calls
                    if call.request.url == self.instance_url
                ]
            ),
        )

    @responses.activate
    def test_skip_floating_ip(self):
        del self.instance["external_ips"]
        del self.params["networks"][0]["floating_ip"]

        self.create_instance()
        self.assertEqual(
            1,
            len(
                [
                    call
                    for call in responses.calls
                    if call.request.url == self.instance_url
                ]
            ),
        )

    @responses.activate
    def test_raise_exception_if_order_item_state_is_erred(self):
        self.order["state"] = "erred"
        self.order["error_message"] = "error message"
        url = self._get_url("marketplace-orders/%s" % self.order["uuid"])
        responses.replace(responses.GET, url, json=self.order, status=200)
        self.assertRaises(WaldurClientException, self.create_instance)

    def create_instance(self):
        self.client.create_instance_via_marketplace(**self.params)
        post_request = [
            call.request for call in responses.calls if call.request.method == "POST"
        ][0]
        return json.loads(post_request.body.decode("utf-8"))


class InstanceDeleteViaMarketplaceTest(BaseWaldurClientTest):
    def setUp(self):
        super(InstanceDeleteViaMarketplaceTest, self).setUp()
        url = self._get_url("marketplace-resources")
        scope_url = self._get_url("scope_url")
        responses.add(
            responses.GET,
            url,
            json=[{"scope": scope_url, "uuid": "resource_uuid"}],
            status=200,
        )
        responses.add(
            responses.GET,
            scope_url,
            json={"name": "instance", "uuid": "6b6e60870ad64085aadcdcbc1fd84a7e"},
            status=200,
        )
        url = self._get_url("marketplace-resources/resource_uuid/terminate")
        responses.add(
            responses.POST, url, json={"order_uuid": "order_uuid"}, status=200
        )

    @responses.activate
    def test_deletion_parameters_are_passed_as_query_parameters(self):
        self.client.delete_instance_via_marketplace("6b6e60870ad64085aadcdcbc1fd84a7e")
        self.assertEqual(
            [c.request.url for c in responses.calls if c.request.method == "POST"][0],
            "http://example.com:8000/api/marketplace-resources/resource_uuid/terminate/",
        )

    @responses.activate
    def test_pass_delete_options_to_api(self):
        self.client.delete_instance_via_marketplace(
            "6b6e60870ad64085aadcdcbc1fd84a7e", release_floating_ips=False
        )
        self.assertEqual(
            [
                json.loads(c.request.body)
                for c in responses.calls
                if c.request.method == "POST"
            ][0],
            {"attributes": {"release_floating_ips": False}},
        )


class InstanceStopTest(BaseWaldurClientTest):
    def setUp(self):
        super(InstanceStopTest, self).setUp()
        self.expected_url = (
            "http://example.com:8000/api/openstack-instances/"
            "6b6e60870ad64085aadcdcbc1fd84a7e/stop/"
        )

    @responses.activate
    def test_valid_url_is_rendered_for_action(self):
        responses.add(
            responses.POST,
            self.expected_url,
            status=202,
            json={"details": "Instance stop has been scheduled."},
        )
        self.client.stop_instance("6b6e60870ad64085aadcdcbc1fd84a7e", wait=False)


class OfferingManagementTest(BaseWaldurClientTest):
    def setUp(self):
        super(OfferingManagementTest, self).setUp()
        self.offering_uuid = "test_offering_uuid"
        self.base_url = "http://example.com:8000/api/marketplace-provider-offerings"
        # Sample order for reuse in tests
        self.sample_order = {
            "offering": f"http://example.com:8000/api/marketplace-public-offerings/{self.offering_uuid}/",
            "offering_name": "Test Offering",
            "offering_uuid": self.offering_uuid,
            "uuid": "order-uuid",
            "created": "2025-02-14T13:55:44.709546+00:00",
            "type": "Create",
            "state": "executing",
            "marketplace_resource_uuid": "test-marketplace-resource-uuid",
            "project_name": "Test Project",
            "project_uuid": "test-project-uuid",
        }

    @responses.activate
    def test_activate_offering_success(self):
        """
        Test that offering can be successfully activated:
        - POST request is made to the correct URL
        - Response state is 'Active'
        """
        url = f"{self.base_url}/{self.offering_uuid}/activate/"
        responses.add(responses.POST, url, status=200, json={"state": "Active"})

        response = self.client.activate_offering(self.offering_uuid)

        self.assertEqual(len(responses.calls), 1, "Expected one API call to be made")
        self.assertEqual(
            response["state"],
            "Active",
            f"Expected state to be 'Active', got '{response.get('state')}'",
        )

    @responses.activate
    def test_activate_offering_error(self):
        """
        Test that appropriate exception is raised when offering activation fails:
        - Should raise WaldurClientException for 400 status
        """
        url = f"{self.base_url}/{self.offering_uuid}/activate/"
        responses.add(
            responses.POST,
            url,
            status=400,
            json={"detail": "No Offering matches the given query."},
        )

        self.assertRaises(
            WaldurClientException, self.client.activate_offering, self.offering_uuid
        )

    @responses.activate
    def test_delete_offering_success(self):
        """
        Test that offering can be successfully deleted:
        - DELETE request is made to the correct URL
        - Status code 204 is handled correctly
        """
        url = f"{self.base_url}/{self.offering_uuid}/"
        responses.add(responses.DELETE, url, status=204)

        self.client.delete_offering(self.offering_uuid)

        self.assertEqual(len(responses.calls), 1, "Expected one API call to be made")
        self.assertEqual(
            responses.calls[0].request.method,
            "DELETE",
            f"Expected DELETE method, got {responses.calls[0].request.method}",
        )

    @responses.activate
    def test_delete_offering_error(self):
        """
        Test that appropriate exception is raised when offering deletion fails:
        - Should raise WaldurClientException for 404 status
        - Should verify correct request method and status code
        """
        url = f"{self.base_url}/{self.offering_uuid}/"
        responses.add(responses.DELETE, url, status=404, json={"detail": "Not found"})

        self.assertRaises(
            WaldurClientException, self.client.delete_offering, self.offering_uuid
        )
        self.assertEqual(
            responses.calls[0].request.method,
            "DELETE",
            f"Expected DELETE method, got {responses.calls[0].request.method}",
        )
        self.assertEqual(
            responses.calls[0].response.status_code,
            404,
            f"Expected status code 404, got {responses.calls[0].response.status_code}",
        )

    @responses.activate
    def test_list_offering_orders(self):
        """
        Test that offering orders can be successfully listed:
        - GET request is made to the correct URL
        - Response contains expected orders
        """
        url = f"{self.base_url}/{self.offering_uuid}/orders/"
        expected_orders = [self.sample_order]
        responses.add(responses.GET, url, status=200, json=expected_orders)

        response = self.client.marketplace_provider_offering_list_orders(
            self.offering_uuid
        )

        self.assertEqual(len(responses.calls), 1, "Expected one API call to be made")
        self.assertEqual(
            response, expected_orders, "Response should match expected orders"
        )
        self.assertEqual(
            responses.calls[0].request.method,
            "GET",
            f"Expected GET method, got {responses.calls[0].request.method}",
        )
        self.assertEqual(
            responses.calls[0].request.url,
            url,
            f"Expected URL {url}, got {responses.calls[0].request.url}",
        )

    @responses.activate
    def test_get_offering_order_details(self):
        """
        Test that specific offering order details can be retrieved:
        - GET request is made to the correct URL
        - Response contains expected order details
        """
        order_uuid = "order-uuid"
        url = f"{self.base_url}/{self.offering_uuid}/orders/{order_uuid}/"
        responses.add(responses.GET, url, status=200, json=self.sample_order)

        response = self.client.marketplace_provider_offering_get_order(
            self.offering_uuid, order_uuid
        )

        self.assertEqual(len(responses.calls), 1, "Expected one API call to be made")
        self.assertEqual(
            response, self.sample_order, "Response should match expected order details"
        )
        self.assertEqual(
            responses.calls[0].request.method,
            "GET",
            f"Expected GET method, got {responses.calls[0].request.method}",
        )

    @responses.activate
    def test_list_offering_orders_with_filters(self):
        """
        Test that offering orders can be filtered:
        - GET request includes filter parameters
        - Response contains filtered orders
        """
        url = f"{self.base_url}/{self.offering_uuid}/orders/"
        filters = {"state": "executing", "created_after": "2025-01-01"}

        # Modify sample order to match filter
        filtered_order = dict(self.sample_order)
        filtered_order["state"] = "executing"
        expected_orders = [filtered_order]

        responses.add(responses.GET, url, status=200, json=expected_orders)

        response = self.client.marketplace_provider_offering_list_orders(
            self.offering_uuid, filters=filters
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(response, expected_orders)

        # Verify that filters were passed correctly
        query_params = responses.calls[0].request.url.split("?")[1]
        self.assertIn("state=executing", query_params)
        self.assertIn("created_after=2025-01-01", query_params)


class SecurityGroupTest(BaseWaldurClientTest):
    security_group = {
        "name": "secure group",
        "uuid": "59e46d029a79473779915a22",
        "state": "OK",
        "rules": [
            {
                "to_port": 10,
                "from_port": 20,
                "cidr": "0.0.0.0/24",
                "protocol": "tcp",
            }
        ],
    }

    @responses.activate
    def test_waldur_client_returns_security_group_by_tenant_name_and_security_group_name(
        self,
    ):
        security_group = dict(name="security_group")
        params = dict(
            name_exact=security_group["name"], tenant_uuid=self.tenant["uuid"]
        )
        get_url = self._get_url("openstack-security-groups", params)
        responses.add(
            responses.GET,
            get_url,
            json=[security_group],
        )
        responses.add(
            responses.GET, self._get_url("openstack-tenants"), json=[self.tenant]
        )

        response = self.client.get_security_group(
            self.tenant["name"], security_group["name"]
        )

        self.assertEqual(response["name"], security_group["name"])

    def create_security_group(self, **kwargs):
        action_name = "create_security_group"
        responses.add(
            responses.GET, self._get_url("openstack-tenants"), json=[self.tenant]
        )
        post_url = self._get_subresource_url(
            "openstack-tenants", self.tenant["uuid"], action_name
        )
        responses.add(responses.POST, post_url, json=self.security_group, status=201)

        instance_url = "%s/openstack-security-groups/%s/" % (
            self.api_url,
            self.security_group["uuid"],
        )
        responses.add(responses.GET, instance_url, json=self.security_group, status=200)

        client = WaldurClient(self.api_url, self.access_token)
        response = client.create_security_group(
            tenant=self.tenant["name"],
            name=self.security_group["name"],
            rules=self.security_group["rules"],
            **kwargs,
        )
        return response

    @responses.activate
    def test_waldur_client_creates_security_group_with_passed_parameters(self):
        response = self.create_security_group()
        self.assertEqual(self.security_group["name"], response["name"])
        self.assertEqual(self.security_group["rules"], response["rules"])

    @responses.activate
    def test_search_tenant_by_project_name(self):
        project = {
            "uuid": str(uuid.uuid4()),
        }
        responses.add(responses.GET, self._get_url("projects"), json=[project])

        self.create_security_group(project="waldur")

        url = [
            call.request.url for call in responses.calls if call.request.method == "GET"
        ][0]
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["name_exact"][0], "waldur")

        url = [
            call.request.url for call in responses.calls if call.request.method == "GET"
        ][1]
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["project_uuid"][0], project["uuid"])


class VolumeDetachTest(BaseWaldurClientTest):
    def setUp(self):
        super(VolumeDetachTest, self).setUp()
        self.expected_url = (
            "http://example.com:8000/api/openstack-volumes/"
            "6b6e60870ad64085aadcdcbc1fd84a7e/detach/"
        )

    @responses.activate
    def test_valid_url_is_rendered_for_action(self):
        responses.add(
            responses.POST,
            self.expected_url,
            status=202,
            json={"details": "detach was scheduled."},
        )
        self.client.detach_volume("6b6e60870ad64085aadcdcbc1fd84a7e", wait=False)


class VolumeAttachTest(BaseWaldurClientTest):
    def setUp(self):
        super(VolumeAttachTest, self).setUp()
        self.expected_url = (
            "http://example.com:8000/api/openstack-volumes/" "volume_uuid/attach/"
        )

    @responses.activate
    def test_valid_url_is_rendered_for_action(self):
        # Arrange
        responses.add(
            responses.POST,
            self.expected_url,
            status=202,
            json={"details": "attach was scheduled."},
        )

        # Act
        self.client.attach_volume(
            "volume_uuid", "instance_uuid", "/dev/vdb", wait=False
        )

        # Assert
        actual = json.loads(responses.calls[0].request.body.decode("utf-8"))
        expected = {
            "instance": "http://example.com:8000/api/openstack-instances/instance_uuid/",
            "device": "/dev/vdb",
        }
        self.assertEqual(expected, actual)


@responses.activate
class TestPaginatedList(BaseWaldurClientTest):
    def test_without_links(self):
        responses.add(
            responses.GET, self._get_url("customers"), json=[{"name": "Customer 1"}]
        )
        result = self.client.list_customers()
        self.assertEqual(result, [{"name": "Customer 1"}])

    def test_list_single_page(self):
        responses.add(
            responses.GET,
            self._get_url("customers"),
            json=[{"name": "Customer 1"}],
            headers={
                "Link": '<http://example.com:8000/api/customers/>; rel="first", <http://example.com:8000/api/customers/>; rel="last"'
            },
        )
        result = self.client.list_customers()
        self.assertEqual(result, [{"name": "Customer 1"}])

    def test_list_multiple_pages(self):
        responses.add(
            responses.GET,
            self._get_url("customers"),
            json=[{"name": "Customer 1"}],
            headers={
                "Link": '<http://example.com:8000/api/customers/>; rel="first", <http://example.com:8000/api/customers/?page=2>; rel="last"'
            },
        )
        responses.add(
            responses.GET,
            self._get_url("customers"),
            json=[{"name": "Customer 2"}],
            headers={
                "Link": '<http://example.com:8000/api/customers/?page=2>; rel="first", <http://example.com:8000/api/customers/?page=2>; rel="last"'
            },
        )

        result = self.client.list_customers()
        self.assertEqual(result, [{"name": "Customer 1"}, {"name": "Customer 2"}])


class MarketplaceRobotAccountTest(BaseWaldurClientTest):
    """
    Test that the marketplace robot account set state methods return a 200 status code
    """

    def setUp(self):
        super(MarketplaceRobotAccountTest, self).setUp()
        self.account_uuid = "test_robot_account_uuid"
        self.base_url = "http://example.com:8000/api/marketplace-robot-accounts"

    @responses.activate
    def test_marketplace_robot_account_set_state_ok(self):
        """Test that robot account state can be set to ok"""
        url = f"{self.base_url}/{self.account_uuid}/set_state_ok/"

        # Need to include a json response because that's what the client will return
        responses.add(
            responses.POST,
            url,
            json={"state": "OK", "uuid": self.account_uuid},
            status=200,
        )

        response = self.client.marketplace_robot_account_set_state_ok(self.account_uuid)

        # Test the processed response (JSON data)
        self.assertEqual(
            response["state"], "OK", f"Expected state 'OK', got {response['state']}"
        )
        self.assertEqual(
            response["uuid"],
            self.account_uuid,
            f"Expected uuid '{self.account_uuid}', got {response['uuid']}",
        )
        self.assertEqual(
            len(responses.calls),
            1,
            f"Expected 1 call to be made, got {len(responses.calls)}",
        )

    @responses.activate
    def test_marketplace_robot_account_set_state_request_deletion(self):
        """
        Test that the marketplace robot account set state request deletion method returns a 200 status code
        """
        url = f"{self.base_url}/{self.account_uuid}/set_state_request_deletion/"
        responses.add(
            responses.POST,
            url,
            json={"state": "REQUEST_DELETION", "uuid": self.account_uuid},
            status=200,
        )
        response = self.client.marketplace_robot_account_set_state_request_deletion(
            self.account_uuid
        )
        self.assertEqual(
            response["state"],
            "REQUEST_DELETION",
            f"Expected state 'REQUEST_DELETION', got {response['state']}",
        )
        self.assertEqual(
            len(responses.calls),
            1,
            f"Expected 1 call to be made, got {len(responses.calls)}",
        )

    @responses.activate
    def test_marketplace_robot_account_set_state_deleted(self):
        """
        Test that the marketplace robot account set state deleted method returns a 200 status code
        """
        url = f"{self.base_url}/{self.account_uuid}/set_state_deleted/"
        responses.add(
            responses.POST,
            url,
            json={"state": "DELETED", "uuid": self.account_uuid},
            status=200,
        )
        response = self.client.marketplace_robot_account_set_state_deleted(
            self.account_uuid
        )
        self.assertEqual(
            response["state"],
            "DELETED",
            f"Expected state 'DELETED', got {response['state']}",
        )
        self.assertEqual(
            len(responses.calls),
            1,
            f"Expected 1 call to be made, got {len(responses.calls)}",
        )

    @responses.activate
    def test_marketplace_robot_account_set_state_erred(self):
        """
        Test that the marketplace robot account set state erred method returns a 200 status code
        """
        url = f"{self.base_url}/{self.account_uuid}/set_state_erred/"
        responses.add(
            responses.POST,
            url,
            json={"state": "ERRED", "uuid": self.account_uuid},
            status=200,
        )
        response = self.client.marketplace_robot_account_set_state_erred(
            self.account_uuid
        )
        self.assertEqual(
            response["state"],
            "ERRED",
            f"Expected state 'ERRED', got {response['state']}",
        )
        self.assertEqual(
            len(responses.calls),
            1,
            f"Expected 1 call to be made, got {len(responses.calls)}",
        )

    @responses.activate
    def test_marketplace_robot_account_set_state_creating(self):
        """
        Test that the marketplace robot account set state creating method returns a 200 status code
        """
        url = f"{self.base_url}/{self.account_uuid}/set_state_creating/"
        responses.add(
            responses.POST,
            url,
            json={"state": "CREATING", "uuid": self.account_uuid},
            status=200,
        )
        response = self.client.marketplace_robot_account_set_state_creating(
            self.account_uuid
        )
        self.assertEqual(
            response["state"],
            "CREATING",
            f"Expected state 'CREATING', got {response['state']}",
        )
        self.assertEqual(
            len(responses.calls),
            1,
            f"Expected 1 call to be made, got {len(responses.calls)}",
        )
