"""Coordinate transforms between the abstract simulation grid and SUMO networks."""


class GridProjection:
    """Maps a cell of the simulation grid onto a SUMO network's own extent.

    The network is the source of truth: ``getBoundary()`` already returns
    net-local metres, so nothing here needs a CRS, a projection string or the
    ``netOffset`` written by netconvert.
    """

    def __init__(self, xmin, ymin, xmax, ymax):
        self.xmin = float(xmin)
        self.ymin = float(ymin)
        self.xmax = float(xmax)
        self.ymax = float(ymax)

    @classmethod
    def from_net(cls, net):
        """Build a projection covering the network's own boundary."""
        xmin, ymin, xmax, ymax = net.getBoundary()
        return cls(xmin, ymin, xmax, ymax)

    @property
    def degenerate(self):
        """True when the boundary encloses no area, so nothing can be mapped."""
        return self.xmax <= self.xmin or self.ymax <= self.ymin

    @property
    def extent_m(self):
        """Width and height in metres of the mapped network."""
        return (self.xmax - self.xmin, self.ymax - self.ymin)

    def cell_to_xy(self, x, y, width, height):
        """Centre of grid cell (x, y) in net-local metres.

        Cell centres are used so no sample can land on the boundary, and y is
        inverted because Mesa row 0 is the north edge of the world while SUMO
        northing grows northward. Mapping y without the inversion mirrors the
        city, which no current figure would reveal.
        """
        px = self.xmin + ((x + 0.5) / width) * (self.xmax - self.xmin)
        py = self.ymax - ((y + 0.5) / height) * (self.ymax - self.ymin)
        return (px, py)
