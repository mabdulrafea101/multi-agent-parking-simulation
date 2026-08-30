"""Tests for the grid-to-network projection."""
import pytest

from engine.geometry import GridProjection


class StubNet:
    def __init__(self, boundary):
        self._boundary = boundary

    def getBoundary(self):
        return self._boundary


def test_cell_centres_land_strictly_inside_the_boundary():
    projection = GridProjection(0.0, 0.0, 1000.0, 1000.0)

    points = [projection.cell_to_xy(x, y, 100, 100)
              for x in (0, 49, 99) for y in (0, 49, 99)]

    assert all(0.0 < px < 1000.0 and 0.0 < py < 1000.0 for px, py in points)


def test_cell_centre_offset_is_half_a_cell():
    projection = GridProjection(0.0, 0.0, 100.0, 100.0)

    assert projection.cell_to_xy(0, 0, 10, 10) == pytest.approx((5.0, 95.0))
    assert projection.cell_to_xy(9, 9, 10, 10) == pytest.approx((95.0, 5.0))


def test_row_zero_is_the_north_edge():
    """Mesa row 0 is the top of the world; SUMO northing grows northward."""
    projection = GridProjection(0.0, 0.0, 1000.0, 1000.0)

    north = projection.cell_to_xy(0, 0, 100, 100)
    south = projection.cell_to_xy(0, 99, 100, 100)

    assert north[1] > south[1]
    assert north[1] == pytest.approx(995.0)
    assert south[1] == pytest.approx(5.0)


def test_columns_increase_eastward():
    projection = GridProjection(10.0, 20.0, 110.0, 120.0)

    west = projection.cell_to_xy(0, 50, 100, 100)
    east = projection.cell_to_xy(99, 50, 100, 100)

    assert east[0] > west[0]
    assert west[0] == pytest.approx(10.5)


def test_non_square_extent_scales_axes_independently():
    """Kuala Lumpur's network shape: 6138.4 m wide by 7762.5 m tall."""
    projection = GridProjection(0.0, 0.0, 6138.4, 7762.5)

    x, y = projection.cell_to_xy(49, 49, 100, 100)

    assert x == pytest.approx(6138.4 * 49.5 / 100)
    assert y == pytest.approx(7762.5 * (1 - 49.5 / 100))


def test_negative_origin_is_preserved():
    """No integer cell hits an exact centre, so assert the origin crossing instead."""
    projection = GridProjection(-500.0, -250.0, 500.0, 250.0)

    west_of_origin = projection.cell_to_xy(49, 50, 100, 100)
    east_of_origin = projection.cell_to_xy(50, 50, 100, 100)

    assert west_of_origin == pytest.approx((-5.0, -2.5))
    assert east_of_origin == pytest.approx((5.0, -2.5))


def test_degenerate_boundary_is_reported():
    assert GridProjection(0.0, 0.0, 0.0, 100.0).degenerate is True
    assert GridProjection(0.0, 0.0, 100.0, 0.0).degenerate is True
    assert GridProjection(100.0, 100.0, 0.0, 0.0).degenerate is True
    assert GridProjection(0.0, 0.0, 100.0, 100.0).degenerate is False


def test_extent_reports_mapped_dimensions():
    projection = GridProjection(-10.0, 5.0, 6128.4, 7767.5)

    assert projection.extent_m == pytest.approx((6138.4, 7762.5))


def test_from_net_reads_the_network_boundary():
    projection = GridProjection.from_net(StubNet((0.0, 0.0, 6138.4, 7762.5)))

    assert (projection.xmin, projection.ymin, projection.xmax, projection.ymax) == (
        0.0,
        0.0,
        6138.4,
        7762.5,
    )
    assert projection.degenerate is False


def test_from_net_handles_a_degenerate_network():
    assert GridProjection.from_net(StubNet((0.0, 0.0, 0.0, 0.0))).degenerate is True
