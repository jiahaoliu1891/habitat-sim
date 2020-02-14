import multiprocessing
import random

import magnum as mn
import numpy as np
import pytest

import examples.settings
import habitat_sim


def test_no_navmesh_smoke():
    sim_cfg = habitat_sim.SimulatorConfiguration()
    agent_config = habitat_sim.AgentConfiguration()
    # No sensors as we are only testing to see if things work
    # with no navmesh and the navmesh isn't used for any exisitng sensors
    agent_config.sensor_specifications = []

    sim_cfg.scene.id = "data/scene_datasets/habitat-test-scenes/van-gogh-room.glb"
    # Make it try to load a navmesh that doesn't exists
    sim_cfg.scene.filepaths["navmesh"] = "/tmp/dne.navmesh"

    sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_config]))

    sim.initialize_agent(0)

    random.seed(0)
    for _ in range(50):
        obs = sim.step(random.choice(list(agent_config.action_space.keys())))
        # Can't collide with no navmesh
        assert not obs["collided"]


def test_empty_scene(sim):
    cfg_settings = examples.settings.default_sim_settings.copy()

    # keyword "NONE" initializes a scene with no scene mesh
    cfg_settings["scene"] = "NONE"
    # test that depth sensor doesn't mind an empty scene
    cfg_settings["depth_sensor"] = True

    hab_cfg = examples.settings.make_cfg(cfg_settings)
    sim.reconfigure(hab_cfg)

    # test that empty frames can be rendered without a scene mesh
    for _ in range(2):
        obs = sim.step(random.choice(list(hab_cfg.agents[0].action_space.keys())))


def test_sim_reset(sim):
    agent_config = sim.config.agents[0]
    sim.initialize_agent(0)
    initial_state = sim.agents[0].initial_state
    # Take random steps in the environment
    for _ in range(10):
        action = random.choice(list(agent_config.action_space.keys()))
        obs = sim.step(action)

    sim.reset()
    new_state = sim.agents[0].get_state()
    same_position = all(initial_state.position == new_state.position)
    same_rotation = np.isclose(
        initial_state.rotation, new_state.rotation, rtol=1e-4
    )  # Numerical error can cause slight deviations
    assert same_position and same_rotation


# Make sure you can keep a reference to an agent alive without crashing
def _test_keep_agent_tgt():
    sim_cfg = habitat_sim.SimulatorConfiguration()
    agent_config = habitat_sim.AgentConfiguration()

    sim_cfg.scene.id = "data/scene_datasets/habitat-test-scenes/van-gogh-room.glb"
    agents = []

    for _ in range(3):
        sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_config]))

        agents.append(sim.get_agent(0))

        sim.close()


# Make sure you can construct and destruct the simulator multiple times
def _test_multiple_construct_destroy_tgt():
    sim_cfg = habitat_sim.SimulatorConfiguration()
    agent_config = habitat_sim.AgentConfiguration()

    sim_cfg.scene.id = "data/scene_datasets/habitat-test-scenes/van-gogh-room.glb"

    for _ in range(3):
        sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_config]))

        sim.close()


@pytest.mark.parametrize(
    "test_fn", [_test_keep_agent_tgt, _test_multiple_construct_destroy_tgt]
)
def test_subproc_fns(test_fn):
    mp_ctx = multiprocessing.get_context("spawn")

    # Run this test in a subprocess as things with OpenGL
    # contexts get messy
    p = mp_ctx.Process(target=test_fn)

    p.start()
    p.join()

    assert p.exitcode == 0


def test_scene_bounding_boxes(sim):
    cfg_settings = examples.settings.default_sim_settings.copy()
    cfg_settings["scene"] = "data/scene_datasets/habitat-test-scenes/van-gogh-room.glb"
    hab_cfg = examples.settings.make_cfg(cfg_settings)
    sim.reconfigure(hab_cfg)
    scene_graph = sim._sim.get_active_scene_graph()
    root_node = scene_graph.get_root_node()
    root_node.compute_cumulative_bb()
    scene_bb = root_node.get_cumulative_bb()
    ground_truth = mn.Range3D.from_size(
        mn.Vector3(-0.775869, -0.0233012, -1.6706), mn.Vector3(6.76937, 3.86304, 3.5359)
    )
    assert ground_truth == scene_bb
