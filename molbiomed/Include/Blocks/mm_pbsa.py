"""
MM-PBSA Setup Block for Horus
"""

import subprocess
from pathlib import Path

from HorusAPI import PluginBlock, PluginVariable, VariableTypes

# Inputs
prmtop_input = PluginVariable(
    id="prmtop_file",
    name="Topology",
    description="Path to the AMBER topology file (.prmtop)",
    type=VariableTypes.FILE,
    allowedValues=[".prmtop"],
)

trajectory_input = PluginVariable(
    id="trajectory_file",
    name="Trajectory",
    description="Path to the MD trajectory file (.nc)",
    type=VariableTypes.FILE,
    allowedValues=[".nc"],
)

# Variables
job_name_variable = PluginVariable(
    id="job_name",
    name="Job Name",
    description="Name for the MM-PBSA job",
    type=VariableTypes.STRING,
    defaultValue="MMPBSA_job",
)

frames_variable = PluginVariable(
    id="frames",
    name="Number of Frames",
    description="Total frames from previous MD",
    type=VariableTypes.INTEGER,
    defaultValue=5000,
)

solvent_mask_variable = PluginVariable(
    id="solvent_mask",
    name="Solvent/Ions Mask",
    description="Mask selecting solvent and ions",
    type=VariableTypes.STRING,
    defaultValue=":WAT:Na+:Cl-",
)

ligand_mask_variable = PluginVariable(
    id="ligand_mask",
    name="Ligand Mask",
    description="Ligand residue mask",
    type=VariableTypes.STRING,
    defaultValue=":LIG",
)

output_prefix_variable = PluginVariable(
    id="output_prefix",
    name="Output Prefix",
    description="Prefix for output files",
    type=VariableTypes.STRING,
    defaultValue="mmpbsa_output",
)

pb_radius_variable = PluginVariable(
    id="pb_radius",
    name="PB/GB Radius Set",
    description="Radius set for PB/GB calculation",
    type=VariableTypes.STRING,
    allowedValues=["mbondi", "mbondi2", "mbondi3"],
    defaultValue="mbondi2",
)

cluster_variable = PluginVariable(
    id="cluster",
    name="Cluster",
    description="Cluster configuration to use",
    type=VariableTypes.STRING,
    allowedValues=["picard", "csuc", "local"],
    defaultValue="local",
)

submit_variable = PluginVariable(
    id="run_now",
    name="Run Immediately",
    description="If true, executes generated MM-PBSA script after setup",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# Outputs
input_file_variable = PluginVariable(
    id="mmpbsa_input_file",
    name="MM-PBSA Input File",
    description="Generated MM-PBSA configuration file (mmpbsa.in)",
    type=VariableTypes.FILE,
)

script_file_variable = PluginVariable(
    id="submission_script",
    name="Submission Script",
    description="Generated execution script (script_mmpbsa.sh)",
    type=VariableTypes.FILE,
)


def run_script(block: PluginBlock):
    """
    Executes the MM-PBSA setup script with provided inputs and variables.
    """
    prmtop = Path(block.inputs[prmtop_input.id])
    traj = Path(block.inputs[trajectory_input.id])

    job_name = str(block.variables[job_name_variable.id])
    frames = int(block.variables[frames_variable.id])
    solvent_mask = str(block.variables[solvent_mask_variable.id])
    ligand_mask = str(block.variables[ligand_mask_variable.id])
    output_prefix = str(block.variables[output_prefix_variable.id])
    pb_radius = str(block.variables[pb_radius_variable.id])
    cluster = str(block.variables[cluster_variable.id])
    run_now = bool(block.variables[submit_variable.id])

    script_location = (
        Path(block.pluginDir)
        / "Include"
        / "protocols"
        / "MM-PBSA"
        / "mmpbsa_setup.sh"
    )

    workdir = Path(block.pluginDir)

    cmd = [
        "bash",
        str(script_location),
        "-j",
        job_name,
        "-t",
        str(traj),
        "-f",
        str(frames),
        "-p",
        str(prmtop),
        "-s",
        solvent_mask,
        "-n",
        ligand_mask,
        "-o",
        output_prefix,
        "-r",
        pb_radius,
        "-q",
        cluster,
    ]

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(workdir),
    ) as process:
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"- Error executing setup script: {stderr}")
            raise RuntimeError(f"MM-PBSA setup failed: {stderr}")
        print(f"Setup stdout:\n{stdout}\nSetup stderr:\n{stderr}")

    script_file = workdir / "script_mmpbsa.sh"
    input_file = workdir / "mmpbsa.in"

    if run_now and script_file.exists():
        run_cmd = ["bash", str(script_file)]
        with subprocess.Popen(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(workdir),
        ) as process:
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"- Error executing MM-PBSA script: {stderr}")
                raise RuntimeError(f"MM-PBSA execution failed: {stderr}")
            print(f"Execution stdout:\n{stdout}\nExecution stderr:\n{stderr}")

    block.setOutput(input_file_variable.id, str(input_file))
    block.setOutput(script_file_variable.id, str(script_file))


mm_pbsa_block = PluginBlock(
    id="mm_pbsa_setup",
    name="MM-PBSA Setup",
    description=(
        "Generate MM-PBSA input and execution script; optional immediate run."
    ),
    inputs=[prmtop_input, trajectory_input],
    variables=[
        job_name_variable,
        frames_variable,
        solvent_mask_variable,
        ligand_mask_variable,
        output_prefix_variable,
        pb_radius_variable,
        cluster_variable,
        submit_variable,
    ],
    outputs=[input_file_variable, script_file_variable],
    action=run_script,
)
