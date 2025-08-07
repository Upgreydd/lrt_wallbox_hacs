# Home Assistant LRT Wallbox Integration

## About
This is a custom integration for Home Assistant that allows you to control and monitor LRT Wallbox.
It supports features such as starting and stopping charging, setting the maximum current, and monitoring the charging status.

### Requirements
In order to use this integration, you need to have the following:
- Home Assistant installed and running.
- An LRT Wallbox with network connectivity.
- HACS (Home Assistant Community Store) installed.

### HACS Installation
Search for "LRT Wallbox" in HACS and install the integration. Alternatively, you can manually [add this repository url as a HACS custom repository](https://hacs.xyz/docs/faq/custom_repositories).

### Configuration
1. Go to Home Assistant's configuration page.
2. Navigate to "Integrations".
3. Click on "Add Integration" and search for "LRT Wallbox".
4. Enter the required details such as IP address, port, and authentication credentials.
5. Save the configuration.

### Troubleshooting
If you encounter any issues, check the following:
- Ensure that the LRT Wallbox is powered on and connected to the network.
- Ensure you have done the initial setup of the LRT Wallbox via its BLE LRT PowerUP application.
- Check the Home Assistant logs for any error messages related to the integration.
- Ensure that the integration is up to date by checking for updates in HACS.
- If you have any issues, please open an issue on the [GitHub repository](https://github.com/Upgreydd/lrt_wallbox_hacs)
- For more detailed troubleshooting, refer to the [Home Assistant documentation](https://www.home-assistant.io/docs/).
- If you have any questions or need help, you can join the [Home Assistant Community](https://community.home-assistant.io/) and ask for assistance.
- If you have suggestions for improvements or new features, feel free to open a feature request on the GitHub repository.
- If you find a bug, please open an issue on the GitHub repository with detailed information about the problem.
- If you want to contribute to the project, feel free to fork the repository and submit a pull request with your changes.

### License
This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
