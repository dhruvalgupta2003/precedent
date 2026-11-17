import pytest
from pydantic_ai import models

from precedent import service
from safety import safe_graph_name


@pytest.mark.parametrize("name", ["precedent", "backstage", "my_test_graph", "test_", "TEST_x", "test_a;DROP", ""])
def test_a_graph_that_is_not_a_test_graph_is_refused(name):
    with pytest.raises(ValueError, match="refusing graph"):
        safe_graph_name(name)


def test_a_test_graph_name_is_accepted_unchanged():
    assert safe_graph_name("test_1234_ab12cd34") == "test_1234_ab12cd34"


def test_a_real_model_request_is_refused_inside_the_test_suite():
    """If this passes, no test can spend money or depend on a provider being up."""
    with pytest.raises(RuntimeError, match="not allowed"):
        models.check_allow_model_requests()


def test_no_test_can_reach_the_users_own_database_or_bundles(tmp_path_factory):
    """A check that isn't faked falls through to the built-in database: it must be a throwaway one, never theirs."""
    throwaway = tmp_path_factory.getbasetemp()

    assert service.database_path().is_relative_to(throwaway)
    assert service.bundle_path("team").is_relative_to(throwaway)
