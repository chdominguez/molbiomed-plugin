"""
Custom MD Simulation Creation Block for Horus
"""

import os
import shutil
import subprocess
from pathlib import Path

from HorusAPI import Extensions, PluginVariable, SlurmBlock, VariableTypes

# Inputs
prmtop_input = PluginVariable(
    id="parameters_file",
    name="Parameters",
    description="Path to the AMBER parameters file (.prmtop)",
    type=VariableTypes.FILE,
    allowedValues=[
        ".prmtop",
        ".top",
        ".parm7",
    ],
)

inpcrd_input = PluginVariable(
    id="coordinates_file",
    name="Coordinates",
    description="Path to the AMBER coordinates file (.inpcrd)",
    type=VariableTypes.FILE,
    allowedValues=[".inpcrd", ".rst7", ".crd", ".rst"],
)

# Variables
temperature_variable = PluginVariable(
    id="temperature",
    name="Temperature (K)",
    description="Simulation temperature in Kelvin",
    type=VariableTypes.FLOAT,
    defaultValue=300.0,
)

length_variable = PluginVariable(
    id="length_ns",
    name="Production Length (ns)",
    description="Total intended production length in nanoseconds",
    type=VariableTypes.INTEGER,
    defaultValue=200,
)

replicas_variable = PluginVariable(
    id="replicas",
    name="Replicas",
    description="Number of independent replicas to generate and submit",
    type=VariableTypes.INTEGER,
    defaultValue=1,
)


last_residue_interactive_variable = PluginVariable(
    id="last_residue_interactive",
    name="Last Residue (Interactive)",
    description=(
        "You can specify the last residue of the solute by clicking on it in"
        " the 3D viewer."
    ),
    type=VariableTypes.RESIDUE,
)
last_residue_variable = PluginVariable(
    id="last_residue",
    name="Last Residue Index",
    description=(
        "Index of last residue of solute for restraints. Will take precedence"
        " over interactive selection."
    ),
    type=VariableTypes.INTEGER,
)

# Outputs
preprod_folder_variable = PluginVariable(
    id="preprod_folder",
    name="Preproduction Folder",
    description="Folder containing MD preproduction outputs",
    type=VariableTypes.FOLDER,
)

prod_folder_variable = PluginVariable(
    id="prod_folder",
    name="Production Folder",
    description="Folder containing MD production outputs",
    type=VariableTypes.FOLDER,
)


def run_script(block: SlurmBlock):
    """Generate and submit one or more replica MD setups."""
    prmtop_path = Path(block.inputs[prmtop_input.id])
    inpcrd_path = Path(block.inputs[inpcrd_input.id])

    temperature_value = float(block.variables[temperature_variable.id])
    length_value = int(block.variables[length_variable.id])
    replicas_value = int(block.variables[replicas_variable.id])

    last_residue_value = block.variables.get(last_residue_variable.id) or (
        block.variables.get(last_residue_interactive_variable.id) or {}
    ).get("residue")

    if not last_residue_value:
        raise ValueError(
            "Last residue must be specified via index or interactive"
            " selection."
        )

    # Get the machine (horus remote)
    machine = block.remote.name
    allowed_machines = ["csuc", "local", "picard", "slurm"]

    if machine not in allowed_machines:
        raise ValueError(
            f"Machine '{machine}' is not supported. Allowed machines are:"
            f" {', '.join(allowed_machines)}. Please update the plugin and the"
            " create_md_custom script to support this machine."
        )

    parent_workdir = Path(os.getcwd()) / "md_custom_workdir"
    if parent_workdir.exists():
        print(
            f"WARNING: existing parent workdir found at {parent_workdir};"
            " removing it now. All prior contents will be permanently"
            " deleted."
        )
        shutil.rmtree(parent_workdir)
    os.makedirs(parent_workdir, exist_ok=True)

    script_location = (
        Path(block.pluginDir)
        / "Include"
        / "protocols"
        / "MD"
        / "cMD"
        / "create_md_custom.sh"
    )

    remote_job_folders = []
    for replica in range(1, replicas_value + 1):
        replica_tag = f"replica_{replica:02d}"
        workdir = parent_workdir / replica_tag
        os.makedirs(workdir, exist_ok=True)

        shutil.copy2(prmtop_path, workdir / prmtop_path.name)
        shutil.copy2(inpcrd_path, workdir / inpcrd_path.name)

        prmtop = prmtop_path.name
        inpcrd = inpcrd_path.name

        out_preprod_folder = workdir / "preprod"
        out_prod_folder = workdir / "prod"

        cmd = [
            "bash",
            str(script_location),
            "-p",
            str(prmtop),
            "-c",
            str(inpcrd),
            "-r",
            str(last_residue_value),
            "-t",
            str(temperature_value),
            "-l",
            str(length_value),
            "-m",
            machine,
        ]

        print(
            f"\n[Replica {replica}/{replicas_value}]\nExecuting script:"
            f" {' '.join(cmd)}"
        )

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(workdir),
        ) as process:
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"Replica {replica} error executing script: {stderr}")
                raise RuntimeError(
                    f"Replica {replica} script failed with error: {stderr}"
                )
            if stdout.strip():
                print(f"Replica {replica} script stdout:\n{stdout}")
            if stderr.strip():
                print(f"Replica {replica} script stderr:\n{stderr}")

        # Log contents
        for folder_path in [out_preprod_folder, out_prod_folder]:
            if folder_path.exists() and folder_path.is_dir():
                print(f"  {replica_tag}/{folder_path.name}/")
            else:
                print(f"  {replica_tag}/{folder_path.name}/ (not found)")

        out_slurm_file = workdir / "script.sh"
        if out_slurm_file.exists():
            Extensions().loadFile(
                str(out_slurm_file), f"{replica_tag}_script.sh", readOnly=True
            )

        if block.remote.isLocal:
            job_id = block.remote.submitJob(str(out_slurm_file))
        else:
            flow_name = block.flow.name.replace(" ", "_")
            remote_root = os.path.join(block.remote.workDir, flow_name)
            print(f"Creating remote root directory at {remote_root}...")
            block.remote.command(f"mkdir -p {remote_root}")
            print("Transferring workdir to remote...")
            remote_workdir = block.remote.sendData(str(workdir), remote_root)
            remote_script_path = os.path.join(
                remote_workdir, out_slurm_file.name
            )
            print("Submitting job on remote...")
            job_id = block.remote.submitJob(remote_script_path)
            remote_job_folders.append(remote_workdir)

        print("Submitted job with ID:", job_id)

    if remote_job_folders:
        block.extraData["remote_job_folders"] = remote_job_folders


def download_data(block: SlurmBlock):
    """
    Download data for all replicas and expose aggregated folders as outputs.
    """
    parent_workdir = Path(os.getcwd()) / "md_custom_workdir"
    if not parent_workdir.exists():
        raise FileNotFoundError(
            "Parent workdir not found; nothing to download."
        )

    replicas_value = int(block.variables[replicas_variable.id])

    if not block.remote.isLocal:
        remote_job_folders = block.extraData.get("remote_job_folders", [])
        if len(remote_job_folders) != replicas_value:
            print(
                "Warning: remote job folders count does not match replicas;"
                " attempting partial download."
            )
        for idx, remote_folder in enumerate(remote_job_folders, start=1):
            replica_tag = f"replica_{idx:02d}"
            local_replica_dir = parent_workdir / replica_tag
            os.makedirs(local_replica_dir, exist_ok=True)
            for sub in ["preprod", "prod"]:
                remote_sub = os.path.join(remote_folder, sub)
                local_sub = local_replica_dir / sub
                print(f"Downloading {sub} for {replica_tag}...")
                block.remote.getData(remote_sub, str(local_sub))

    aggregated_preprod = parent_workdir / "preprod_replicas"
    aggregated_prod = parent_workdir / "prod_replicas"
    os.makedirs(aggregated_preprod, exist_ok=True)
    os.makedirs(aggregated_prod, exist_ok=True)

    for replica in range(1, replicas_value + 1):
        replica_tag = f"replica_{replica:02d}"
        rep_dir = parent_workdir / replica_tag
        for sub, agg in [
            ("preprod", aggregated_preprod),
            ("prod", aggregated_prod),
        ]:
            src = rep_dir / sub
            if src.exists():
                link_name = agg / f"{replica_tag}_{sub}"
                if not link_name.exists():
                    try:
                        os.symlink(src, link_name)
                    except OSError:
                        with open(link_name, "w", encoding="utf-8") as fh:
                            fh.write(str(src))

    block.setOutput(preprod_folder_variable.id, str(aggregated_preprod))
    block.setOutput(prod_folder_variable.id, str(aggregated_prod))


custom_md_block = SlurmBlock(
    id="create_md_custom",
    name="Create Custom MD Simulation",
    description=(
        "Generate preproduction and production MD inputs and run pipeline."
    ),
    inputs=[prmtop_input, inpcrd_input],
    variables=[
        temperature_variable,
        length_variable,
        replicas_variable,
        last_residue_interactive_variable,
        last_residue_variable,
    ],
    outputs=[preprod_folder_variable, prod_folder_variable],
    initialAction=run_script,
    finalAction=download_data,
)
