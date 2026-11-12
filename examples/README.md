# Fictional engineering example

Run `python tools/run_demo.py --output runs/demo` from the repository root.

The two files under `demo/text/` are original fictional passages, not UN reports. Their future document symbols only exercise the PKOC filename/header parser. They have no official source links. Orin Kelm, Lina Daro, and Mara Venn are fictional names in this example.

`demo_server.py` serves **scripted responses on loopback**. It is not a language model and recognizes only these fictional names. It exercises the same HTTP adapter, prompts, response validation, grounding, identity resolution, role coding, projection, and export path used by `tools/run_case.py`. The server stops when the command ends. No external service, account, model, or paid request is used.

Expected result: five numbered paragraphs, three actors, and one paragraph-scale edge with weight two. Mara Venn remains an isolate at paragraph scale; all three actors co-occur at report scale. Valid empty extraction is represented by the paragraph without named people.

Open the `index.html` path printed by the command, or load `runs/demo/bundle.json` through **Use your data → Open local dataset** on the public explorer. To inspect the fictional paragraphs locally, add `runs/demo/prepared.json` with **Add local source text**.

This is a software demonstration, not a model evaluation, new dataset, comparative study, or research finding. For actual model inference on your reports, follow [the setup guide](../docs/quickstart.md). Example code is MIT; the original fictional passages are CC BY 4.0.
