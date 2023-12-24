import json
from src import graph as graphbook
import os
import logging


def report_unfilled_onnx_primitives(root_op: graphbook.Operation) -> None:
    """ Report a list of unfilled primitives. """

    all_unfilled = graphbook.get_all_unfilled_composites(root_op)
    for op in all_unfilled:
        logging.info(f"Unfilled composite: {op.name}, type: {op.primitive_name}, inputs: {op.inputs}, outputs: {op.outputs}")


def simplify_names_in_place(root_op: graphbook.Operation) -> None:
    """ Simplify the names of the operations in place, by removing the full path. """

    if root_op.links is not None:
        for link in root_op.links:
            last_piece = link.source.operation.split("/")[-1]
            link.source.operation = last_piece

            last_piece = link.sink.operation.split("/")[-1]
            link.sink.operation = last_piece

    if root_op.operations is not None:
        for op in root_op.operations:
            last_piece = op.name.split("/")[-1]
            op.name = last_piece

            if op.operations is not None and len(op.operations) > 0:
                simplify_names_in_place(op)


def add_boot_flow_state_in_place(root_op: graphbook.Operation) -> None:
    """ Add the boot flow state to all inputs with data. """

    for op in root_op.operations:
        if op.inputs is not None:
            for inp in op.inputs:
                if inp.data is not None:
                    inp.flow_state = graphbook.FlowState.BOOT_SOURCE

        if op.operations is not None and len(op.operations) > 0:
            add_boot_flow_state_in_place(op)


def remap_weight_paths_in_place(
        root_op: graphbook.Operation,
        old_path: str,
        new_path: str,
        do_write=False,
        update_op=True) -> None:
    """ Remap the weight paths to the new directory."""

    all_prims = graphbook.get_all_primitives(root_op)
    read_list = [prim for prim in all_prims if prim.primitive_name in ["read_from_file"]]#, "write_to_file"]]

    file_change_map = {}
    for prim in read_list:
        # First item is the dir name
        # Second item is the file name
        dir_name = prim.inputs[0].data
        file_name = prim.inputs[1].data
        # print(f"dir_name: {dir_name}, file_name: {file_name}")
        if dir_name is None:
            dir_part = prim.name.split("onnx::")[0]
            file_change_map[f"{file_name}.json"] = f"{dir_part}{file_name}.json"
        else:
            dir_part = str(dir_name).replace(".", "/")
            file_change_map[f"{dir_name}.{file_name}.json"] = f"{dir_part}/{file_name}.json"

        if update_op:
            # Directory path
            if not dir_part.startswith("/"):
                dir_part = "/" + dir_part

            prim.inputs[0].data = dir_part
            prim.inputs[1].data = f"{file_name}.json"

    if do_write:
        for key, value in file_change_map.items():
            directory = new_path + "/" + "/".join(value.split("/")[:-1])
            if not os.path.exists(directory):
                os.makedirs(directory)

            print(f"{key} -> {value}")
            os.system(f"cp {old_path}/{key} {new_path}/{value}")


if __name__ == "__main__":
    graphbook_dir = "./llama2-graphbook"
    graphbook_json_file = "model.onnx_v1.json"
    graphbook_json_path = f"{graphbook_dir}/{graphbook_json_file}"

    weight_path = "./llama2_onnx/model.onnx_weights"
    remapped_path = "./llama2_onnx/model.onnx_weights_remapped"

    graphbook_json = json.load(open(graphbook_json_path))
    graphbook_op = graphbook.Operation(**graphbook_json)
    remap_weight_paths_in_place(
        graphbook_op,
        weight_path,
        remapped_path,
        do_write=False,
        update_op=True
    )

    # Write root_op to file
    with open(f"{graphbook_dir}/{graphbook_json_file}_remapped.json", 'w') as f:
        f.write(graphbook_op.model_dump_json(indent=4, exclude_none=True))