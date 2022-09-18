import unittest

import numpy as np
import sympy
from numpy.testing import assert_array_almost_equal

import findiff.core.matrix
from findiff import Diff, EquidistantGrid, Spacing
from findiff import InvalidGrid, InvalidArraySize
from findiff.api import matrix_repr, stencils_repr
from findiff.conflicts import Coef
from findiff.core.algebraic import Add
from findiff.core.deriv import PartialDerivative


class TestDiff(unittest.TestCase):

    def make_grid2d(self):
        x = y = np.linspace(0, 1, 101)
        dx = dy = x[1] - x[0]
        X, Y = np.meshgrid(x, y, indexing='ij')
        return X, Y, dx, dy

    def test_single_first_diff(self):
        x = np.linspace(0, 1, 101)
        dx = x[1] - x[0]
        f = x ** 4
        D = Diff(0)
        actual = D(f, acc=4, spacings={0: dx})
        expected = 4 * x ** 3
        assert_array_almost_equal(expected, actual)

    def test_single_diff(self):
        x = np.linspace(0, 1, 101)
        dx = x[1] - x[0]
        f = x ** 4
        D = Diff(0, 2)
        actual = D(f, acc=4, spacings={0: dx})
        expected = 12 * x ** 2
        assert_array_almost_equal(expected, actual)

    def test_single_diff_along_axis1(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 3 + Y ** 3
        D = Diff(1, 2)
        actual = D(f, acc=4, spacings={1: dx})
        expected = 6 * Y
        assert_array_almost_equal(expected, actual)

    def test_mixed_diff(self):
        X, Y, dx, dy = self.make_grid2d()
        dy = dx
        f = X ** 3 * Y ** 3
        D = Diff({0: 1, 1: 2})
        actual = D(f, acc=4, spacings={0: dx, 1: dy})
        expected = 18 * X ** 2 * Y
        assert_array_almost_equal(expected, actual)

    def test_mixed_diff_default_acc2(self):
        X, Y, dx, dy = self.make_grid2d()
        dy = dx
        f = X ** 3 * Y ** 3
        D = Diff({0: 1, 1: 2})
        expected = 18 * X ** 2 * Y

        actual_acc2 = D(f, spacings={0: dx, 1: dy})
        max_err_acc2 = np.max(np.abs(expected - actual_acc2))

        actual_acc4 = D(f, acc=4, spacings={0: dx, 1: dy})
        max_err_acc4 = np.max(np.abs(expected - actual_acc4))

        assert max_err_acc2 > 1000 * max_err_acc4

    def test_apply_diff_with_single_spacing_defaults_to_same_for_all_axes(self):
        x = np.linspace(0, 1, 101)
        dx = x[1] - x[0]
        f = np.sin(x)

        # Define the derivative:
        d_dx = Diff(0, 1)

        df_dx = d_dx(f, acc=4, spacings=dx)
        assert_array_almost_equal(np.cos(x), df_dx)

    def test_diff_constructor_with_invalid_args_raises_exception(self):
        with self.assertRaises(ValueError):
            Diff(1, 2, 3)

        with self.assertRaises(ValueError):
            Diff(-1)

        with self.assertRaises(ValueError):
            Diff(1, -1)

        with self.assertRaises(ValueError):
            Diff('a')

        with self.assertRaises(ValueError):
            Diff({0: 1, 1: -2})

        with self.assertRaises(TypeError):
            Diff({0: 1, 1: -2}, acc=2)  # acc may not be used on the constructor

        with self.assertRaises(TypeError):
            Diff({0: 1, 1: -2}, 2)

    def test_applying_diff_without_spacing_raises_exception(self):
        D = Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            D(np.ones((10, 10)))

    def test_applying_diff_with_invalid_nondict_spacing_raises_exception(self):
        D = Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            D(np.ones((10, 10)), spacings=-0.1)

    def test_applying_diff_with_nonpositive_spacing_raises_exception(self):
        D = Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            D(np.ones((10, 10)), spacings={1: -0.1})

    def test_apply_diff_to_too_small_array_raises_exception(self):
        x = np.linspace(0, 1, 101)
        D = Diff(10, 1)
        with self.assertRaises(InvalidArraySize):
            D(x ** 2, spacings=0.01)

    def test_single_diff_along_axis1_raises_exception_when_no_spacing_defined_along_axis(self):
        f = np.ones((10, 10))
        D = Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            # should raise exception because given spacing is along axis 0, but
            # derivative is along axis 1.
            D(f, spacings={0: 0.1})

    def test_linear_combination_2d(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 4 + X ** 2 * Y ** 2 + Y ** 4

        D = Diff(0, 2) + 2 * Diff(0) * Diff(1) + Diff(1, 2)
        actual = D(f, acc=4, spacings={0: dx, 1: dy})

        expected = 12 * X ** 2 + 2 * X ** 2 + 2 * Y ** 2 + 8 * X * Y + 12 * Y ** 2
        assert_array_almost_equal(expected, actual)

    def test_linear_combination_2d_with_const_coefs_different_orders(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 4 + X ** 2 * Y ** 2 + Y ** 4

        D1 = Diff(0, 2) + 2 * Diff(0) * Diff(1) + Diff(1, 2)
        actual1 = D1(f, acc=4, spacings={0: dx, 1: dy})

        D2 = Diff(0, 2) + Diff(0) * 2 * Diff(1) + Diff(1, 2)
        actual2 = D2(f, acc=4, spacings={0: dx, 1: dy})

        D3 = Diff(0, 2) + Diff(0) * Diff(1) * 2 + Diff(1, 2)
        actual3 = D3(f, acc=4, spacings={0: dx, 1: dy})

        expected = 12 * X ** 2 + 2 * X ** 2 + 2 * Y ** 2 + 8 * X * Y + 12 * Y ** 2
        assert_array_almost_equal(expected, actual1)
        assert_array_almost_equal(expected, actual2)
        assert_array_almost_equal(expected, actual3)

    def test_linear_combination_2d_with_var_coefs(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 2 * Y ** 2

        D = Coef(X) * Diff(0)
        actual = D(f, spacings={0: dx, 1: dy})
        expected = 2 * f
        assert_array_almost_equal(expected, actual)

    def test_linear_combination_2d_with_var_coefs_product_rule(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 2 * Y ** 2

        # When applying the following differential operator, the
        # product rule must be obeyed:
        D = Diff(0) * X
        actual = D(f, acc=4, spacings={0: dx, 1: dy})
        expected = 3 * f
        assert_array_almost_equal(expected, actual)

        # Alternative syntax (recommended because it is symmetric)
        D = Diff(0) * Coef(X)
        actual = D(f, acc=4, spacings={0: dx, 1: dy})
        expected = 3 * f
        assert_array_almost_equal(expected, actual)

    def test_chaining(self):
        X, Y, dx, dy = self.make_grid2d()
        f = X ** 4 + X ** 2 * Y ** 2 + Y ** 4

        D1 = (Diff(0) - Diff(1)) * (Diff(0) + Diff(1))
        D2 = Diff(0, 2) - Diff(1, 2)
        actual1 = D1(f, acc=4, spacings={0: dx, 1: dy})
        actual2 = D2(f, acc=4, spacings={0: dx, 1: dy})

        expected = 12 * X ** 2 + 2 * Y ** 2 - 12 * Y ** 2 - 2 * X ** 2
        assert_array_almost_equal(expected, actual1)
        assert_array_almost_equal(expected, actual2)


class TestCoefficients(unittest.TestCase):

    def test_can_be_called_with_acc_and_default_symbolics(self):
        import findiff
        out = findiff.coefficients(2, 2, symbolic=True)
        assert isinstance(out['center']['coefficients'][1], sympy.Integer)

    def test_can_be_called_with_offsets(self):
        import findiff
        out = findiff.coefficients(2, offsets=[0, 1, 2, 3], symbolic=True)
        some_coef = out['coefficients'][1]
        assert isinstance(some_coef, sympy.Integer)
        assert some_coef == -5

    def test_must_specify_exactly_one(self):
        import findiff
        with self.assertRaises(ValueError):
            findiff.coefficients(2, acc=2, offsets=[-1, 0, 1])


class TestMatrixRepr(unittest.TestCase):

    def test_matrix_repr_of_second_deriv_1d_acc2(self):
        x = np.linspace(0, 6, 7)
        d2_dx2 = Diff(0, 2)
        actual = matrix_repr(d2_dx2, shape=x.shape, spacings={0: 1})

        expected = [[2, - 5, 4, - 1, 0, 0, 0],
                    [1, - 2, 1, 0, 0, 0, 0],
                    [0, 1, - 2, 1, 0, 0, 0, ],
                    [0, 0, 1, - 2, 1, 0, 0, ],
                    [0, 0, 0, 1, - 2, 1, 0, ],
                    [0, 0, 0, 0, 1, - 2, 1, ],
                    [0, 0, 0, - 1, 4, - 5, 2, ]]

        assert_array_almost_equal(actual.toarray(), expected)

    def test_matrix_repr_laplace_2d(self):
        laplace = Diff(0, 2) + Diff(1, 2)
        actual = matrix_repr(laplace, shape=(10, 10), spacings={0: 1, 1: 1})
        expected = findiff.core.matrix.matrix_repr(Add(PartialDerivative({0: 2}), PartialDerivative({1: 2})),,
        assert_array_almost_equal(actual.toarray(), expected.toarray())

    def test_matrix_repr_with_single_spacing(self):
        laplace = Diff(0, 2) + Diff(1, 2)
        actual = matrix_repr(laplace, shape=(10, 10), spacings=1)
        expected = findiff.core.matrix.matrix_repr(Add(PartialDerivative({0: 2}), PartialDerivative({1: 2})),,
        assert_array_almost_equal(actual.toarray(), expected.toarray())

    def test_matrix_repr_with_negative_spacing_raises_exception(self):
        laplace = Diff(0, 2) + Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            matrix_repr(laplace, shape=(10, 10), spacings=-1)

    def test_matrix_repr_with_incomplete_spacing_raises_exception(self):
        laplace = Diff(0, 2) + Diff(1, 2)
        with self.assertRaises(InvalidGrid):
            matrix_repr(laplace, shape=(10, 10), spacings={1: 1})

    def test_matrix_repr_with_invalid_shape_raises_exception(self):
        laplace = Diff(0, 2) + Diff(1, 2)
        with self.assertRaises(InvalidGrid) as e:
            matrix_repr(laplace, shape=10, spacings={1: 1})
            assert 'must be tuple' in str(e)

    def test_matrix_repr_with_single_spacing_applied(self):
        num_pts = 100
        shape = num_pts, num_pts
        x = y = np.linspace(0, 1, num_pts)
        X, Y = np.meshgrid(x, y, indexing='ij')
        f = X ** 2 + Y ** 2
        h = x[1] - x[0]

        laplace = Diff(0, 2) + Diff(1, 2)
        matrix = matrix_repr(laplace, shape=shape, spacings=h)
        actual = matrix.dot(f.reshape(-1)).reshape(shape)

        expected = 4 * np.ones_like(f)
        assert_array_almost_equal(expected, actual)


class TestStencils(unittest.TestCase):

    def test_stencils_for_d_dx(self):
        d_dx = Diff(0)
        acc = 2
        ndims = 1
        actual = stencils_repr(d_dx, Spacing(1), ndims, acc)
        expected = {
            ('L',): {(0,): -1.5, (1,): 2.0, (2,): -0.5},
            ('C',): {(-1,): -0.5, (0,): 0.0, (1,): 0.5},
            ('H',): {(-2,): 0.5, (-1,): -2.0, (0,): 1.5}}

        for pos in [('L',), ('C',), ('H',)]:
            self.assertEqual(expected[pos], actual[pos].as_dict())
