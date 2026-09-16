# Local validation controller

`make validate` is the sole manual entry point and invokes [`validate`](validate). That script
parses the selected fixture manifest and coordinates the Ansible run. Configure the explicit
Ansible inventory, fixture manifest, optional group, and report directory as shown in
`controller.env.example`. No automatic triggers or production discovery are used.
