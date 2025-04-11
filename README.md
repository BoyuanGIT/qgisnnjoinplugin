QGIS NNJoin Plugin
================

A QGIS plugin that performs a nearest neighbour join on two
vector layers.

For each feature of the input layer, the nearest feature of
the join layer is found, and the distance between the two
features is calculated.

The result of the operation is a new vector layer.
A feature in the result layer will have the geometry and
attributes of one of the features in the input layer plus the
attributes of the nearest feature in the join layer.  In
addition, a new attribute is added that contains the distance
between the two neighbouring features.

Unfortunately, Håvard Tveite, who made significant contributions 
to the development of QGIS and was the author of the NNJoin plugin, 
passed away in May 2021 due to brain cancer.
https://www.qgis.no/2022/05/04/qgis-aerer-havard-tveite/