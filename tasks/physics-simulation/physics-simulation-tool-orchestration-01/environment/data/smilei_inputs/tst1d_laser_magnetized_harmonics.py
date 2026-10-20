# Smilei-style 1D laser-plasma harmonic-generation benchmark snapshot
import math

omega0 = 0.9817477042468103
laser_a0 = 1.65
B0z = 0.72

Main(
    geometry = "1Dcartesian",
    interpolation_order = 2,
    timestep = 0.05,
    simulation_time = 204.8,
    cell_length = [0.05],
    grid_length = [80.0],
    number_of_patches = [8],
    EM_boundary_conditions = [["silver-muller"]],
    reference_angular_frequency_SI = omega0,
)

ExternalField(
    field = "Bz",
    profile = B0z,
)

LaserPlanar1D(
    box_side = "xmin",
    a0 = laser_a0,
    omega = omega0,
    polarization_phi = 0.0,
    ellipticity = 0.0,
)

Species(
    name = "electron",
    position_initialization = "regular",
    momentum_initialization = "cold",
    particles_per_cell = 64,
    mass = 1.0,
    charge = -1.0,
    number_density = 0.18,
    boundary_conditions = [["reflective", "reflective"]],
)

Species(
    name = "ion",
    position_initialization = "regular",
    momentum_initialization = "cold",
    particles_per_cell = 16,
    mass = 1836.0,
    charge = 1.0,
    number_density = 0.18,
    boundary_conditions = [["reflective", "reflective"]],
)

DiagProbe(
    every = 1,
    origin = [0.0],
    corners = [[80.0]],
    number = [1],
    fields = ["Ey", "Bz", "Rho", "Jx"],
)

DiagFields(
    every = 16,
    fields = ["Ey", "Bz", "Rho"],
)

DiagScalar(every = 16)
