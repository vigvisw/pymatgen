# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

from __future__ import division, unicode_literals

import logging

from pymatgen import MPRester
from pymatgen.analysis.phase_diagram import PhaseDiagram, PDPlotter, PDEntry
from pymatgen.analysis.reaction_calculator import ComputedReaction
import numpy as np
from anytree import Node, RenderTree, PreOrderIter


__author__ = "Alex Dunn, Anubhav Jain, Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"


class PDSynthesisTree:

    """
    This class generates a synthesis tree using a phase diagram analysis.
    Starting from a given composition, it iteratively breaks down likely
    synthesis paths up to a certain number of elements, e.g., binaries or
    elements.
    """

    def __init__(self, entries, target, max_nelements=2):
        """
        Args:
            entries ([ComputedEntry]): The computed entries from which to
                perform the phase diagram analysis.
            target (Composition/str): Target composition to get synthesis tree
                for.
            max_nelements (float): This sets a limit as to how many
                elements each reactant should have before the analysis is
                stopped. Default is 2 for binaries. Set to 1 for elements.
        """
        self.pd = PhaseDiagram(entries)
        self.stable_entries = self.pd.stable_entries
        self.max_nelements = max_nelements
        self.target = PDEntry(target, 0)

        def _get_tree(parent, to_remove):
            # Recursive algo to get all reactions
            to_remove = set(to_remove)
            to_remove.add(self.target.composition.reduced_formula)
            new_stable = [e for e in self.stable_entries if
                          e.composition.reduced_formula not in to_remove]
            pd = PhaseDiagram(new_stable)
            decomp = pd.get_decomposition(self.target.composition)

            rxn = ComputedReaction(
                sorted([e for e in decomp.keys()],
                       key=lambda e: e.composition.reduced_formula),
                [self.target])
            rx_str = str(rxn).split("-")[0]
            avg_nel = np.mean([len(e.composition) for e in decomp.keys()])
            child = Node(rx_str, parent, decomp=decomp, avg_nelements=avg_nel,
                         rxn=rxn)
            for e in decomp.keys():
                if not len(e.composition) <= self.max_nelements:
                    to_remove.add(e.composition.reduced_formula)
                    _get_tree(child, to_remove)
            return parent

        rxn = ComputedReaction([self.target], [self.target])
        t = Node(self.target.composition.reduced_formula,
                 decomp={self.target: 1},
                 avg_nelements=len(target), rxn=rxn)

        self.rxn_tree = _get_tree(t, set())

    def get_unique_reactions(self):
        nodes = []
        names = set()
        for pre, fill, node in RenderTree(self.rxn_tree):
            if node.name not in names:
                nodes.append(node)
                names.add(node.name)

        return sorted(nodes, key=lambda n: n.avg_nelements)

    def get_pathways(self):
        pathways = []
        for n in PreOrderIter(self.rxn_tree):
            if len(n.children) == 0:
                k = n
                path = [k]
                while k.parent:
                    k = k.parent
                    path.append(k)
                pathways.append(path)

        for p in pathways:
            ref = p[0].rxn.calculated_reaction_energy
            for k in p:
                print("%s, %.3f" % (k.name, k.rxn.calculated_reaction_energy - ref))

        return pathways

    @classmethod
    def from_mp(cls, chemsys, **kwargs):
        mpr = MPRester()
        entries = mpr.get_entries_in_chemsys(chemsys)
        return PDSynthesisTree(entries, **kwargs)

    def print(self):
        for pre, fill, node in RenderTree(self.rxn_tree):
            output = "%s%s (avg_nelements = %.2f, energy = %.3f)" % (
                    pre, node.name, node.avg_nelements,
                    node.rxn.calculated_reaction_energy)
            print(output)


from pymatgen.util.testing import PymatgenTest


class PDSynthesisTreeTest(PymatgenTest):

    @classmethod
    def setUpClass(cls):
        from monty.serialization import loadfn
        import pymatgen
        import os
        test_path = os.path.join(
            os.path.abspath(os.path.dirname(pymatgen.__file__)), "..",
            "test_files")
        cls.lfo_entries = loadfn(os.path.join(test_path, "Li-Fe-O.json"))

    def test_func(self):
        target = "LiFeO2"
        rxn_tree = PDSynthesisTree(self.lfo_entries, target)
        rxn_tree.print()

        # This breaks everything to elements
        a = PDSynthesisTree(self.lfo_entries, target, 1)
        rxn_tree.print()

        for rxn in a.get_unique_reactions():
            print("%s (avg_nelements = %.2f)" % (rxn.name, rxn.avg_nelements))
        rxn_tree.get_pathways()


if __name__ == "__main__":
    import unittest
    unittest.main()
