# Superseded benchmark

Do not use this directory for the paper's raw-FLUX baseline comparison.

That earlier protocol gave both conditions a long educational prompt and scored the pipeline's unlabeled base PNG. It therefore did not match the intended end-to-end comparison shown in the reference screenshots.

Use `../end-to-end-baseline/` instead. The corrected protocol sends the one-word prompt directly to raw FLUX.1-dev and compares it with the final prompt-enhanced, Qwen-labeled pipeline artifact.
