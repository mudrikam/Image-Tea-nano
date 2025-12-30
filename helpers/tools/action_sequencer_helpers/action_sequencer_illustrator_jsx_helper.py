import os
import json
import time
from datetime import datetime
from config import BASE_PATH
from database.db_operation import ImageTeaDB


class IllustratorJSXGenerator:
    def __init__(self, exec_path=None):
        self.db = ImageTeaDB()
        self.exec_path = exec_path
        self.jsx_dir = os.path.join(BASE_PATH, 'temp', 'jsx', 'illustrator')
        self.temp_dir = os.path.join(BASE_PATH, 'temp', 'illustrator_resident')
        os.makedirs(self.jsx_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.heartbeat_file = os.path.join(self.temp_dir, 'heartbeat.txt')
        self.command_file = os.path.join(self.temp_dir, 'command.json')
        self.resident_jsx = os.path.join(self.jsx_dir, 'ImageTea_Resident.jsx')
    
    def is_resident_alive(self):
        """Check if resident script is running by checking heartbeat"""
        if not os.path.exists(self.heartbeat_file):
            return False
        
        try:
            with open(self.heartbeat_file, 'r') as f:
                timestamp = float(f.read().strip())
            
            # Heartbeat fresh if less than 5 seconds old
            age = time.time() - timestamp
            return age < 5
        except:
            return False
    
    def generate_resident_jsx(self):
        """Generate resident script that stays alive and listens for commands"""
        jsx = []
        jsx.append("// Image Tea Resident Script for Illustrator")
        jsx.append("// This script stays alive and executes commands from Image Tea")
        jsx.append("")
        
        # Paths
        heartbeat_path = self.heartbeat_file.replace('\\', '/')
        command_path = self.command_file.replace('\\', '/')
        
        jsx.append(f"var heartbeatFile = File('{heartbeat_path}');")
        jsx.append(f"var commandFile = File('{command_path}');")
        jsx.append("var running = true;")
        jsx.append("var config = {};")
        jsx.append("")
        
        jsx.append("function updateHeartbeat() {")
        jsx.append("    heartbeatFile.open('w');")
        jsx.append("    heartbeatFile.write(new Date().getTime() / 1000);")
        jsx.append("    heartbeatFile.close();")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeCommand(cmd) {")
        jsx.append("    try {")
        jsx.append("        var preset_id = cmd.preset_id;")
        jsx.append("        var steps = cmd.steps;")
        jsx.append("        var files = cmd.files || [];")
        jsx.append("        var isBatch = cmd.is_batch || false;")
        jsx.append("        var isSingleRunWithFile = cmd.is_single_run_with_file || false;")
        jsx.append("        config = cmd.config || {};")
        jsx.append("        config.outputPath = cmd.output_path || '';")
        jsx.append("        config.prefix = config.output_prefix || '';")
        jsx.append("        config.suffix = config.output_suffix || '';")
        jsx.append("")
        jsx.append("        if (isBatch) {")
        jsx.append("            for (var i = 0; i < files.length; i++) {")
        jsx.append("                var doc = app.open(new File(files[i]));")
        jsx.append("                executeSteps(steps);")
        jsx.append("                doc.close(SaveOptions.DONOTSAVECHANGES);")
        jsx.append("            }")
        jsx.append("        } else if (isSingleRunWithFile && files.length > 0) {")
        jsx.append("            var doc = app.open(new File(files[0]));")
        jsx.append("            executeSteps(steps);")
        jsx.append("            doc.close(SaveOptions.DONOTSAVECHANGES);")
        jsx.append("        } else {")
        jsx.append("            executeSteps(steps);")
        jsx.append("        }")
        jsx.append("        ")
        jsx.append("        running = false;")
        jsx.append("    } catch(e) {")
        jsx.append("        $.writeln('Error executing command: ' + e.message);")
        jsx.append("        running = false;")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeSteps(steps) {")
        jsx.append("    for (var i = 0; i < steps.length; i++) {")
        jsx.append("        var step = steps[i];")
        jsx.append("        if (step.type == 'Action') {")
        jsx.append("            app.doScript(step.name, step.action_set, false);")
        jsx.append("        } else if (step.type == 'Delay') {")
        jsx.append("            $.sleep(step.delay);")
        jsx.append("        } else if (step.type == 'Script') {")
        jsx.append("            eval(step.code);")
        jsx.append("            if (step.delay > 0) $.sleep(step.delay);")
        jsx.append("        } else if (step.type == 'Export') {")
        jsx.append("            executeExport(step.export_format);")
        jsx.append("        }")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function executeExport(format) {")
        jsx.append("    try {")
        jsx.append("        var doc = app.activeDocument;")
        jsx.append("        var fileName = doc.name.replace(/\\.[^.]+$/, '');")
        jsx.append("        var exportFile;")
        jsx.append("        ")
        jsx.append("        if (format == 'PNG') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.png');")
        jsx.append("            var pngOptions = new ExportOptionsPNG24();")
        jsx.append("            pngOptions.transparency = true;")
        jsx.append("            doc.exportFile(exportFile, ExportType.PNG24, pngOptions);")
        jsx.append("        } else if (format == 'JPG' || format == 'JPEG') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.jpg');")
        jsx.append("            var jpgOptions = new ExportOptionsJPEG();")
        jsx.append("            jpgOptions.qualitySetting = 100;")
        jsx.append("            doc.exportFile(exportFile, ExportType.JPEG, jpgOptions);")
        jsx.append("        } else if (format == 'AI') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.ai');")
        jsx.append("            doc.saveAs(exportFile);")
        jsx.append("        } else if (format == 'EPS') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.eps');")
        jsx.append("            var epsOptions = new EPSSaveOptions();")
        jsx.append("            epsOptions.compatibility = Compatibility.ILLUSTRATOR10;")
        jsx.append("            doc.saveAs(exportFile, epsOptions);")
        jsx.append("        } else if (format == 'PDF') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.pdf');")
        jsx.append("            var pdfOptions = new PDFSaveOptions();")
        jsx.append("            doc.saveAs(exportFile, pdfOptions);")
        jsx.append("        } else if (format == 'SVG') {")
        jsx.append("            exportFile = new File(config.outputPath + '/' + config.prefix + fileName + config.suffix + '.svg');")
        jsx.append("            var svgOptions = new ExportOptionsSVG();")
        jsx.append("            doc.exportFile(exportFile, ExportType.SVG, svgOptions);")
        jsx.append("        }")
        jsx.append("        $.sleep(500);")
        jsx.append("    } catch(e) {")
        jsx.append("        $.writeln('Export error: ' + e.message);")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("function checkCommand() {")
        jsx.append("    if (commandFile.exists) {")
        jsx.append("        commandFile.open('r');")
        jsx.append("        var cmdText = commandFile.read();")
        jsx.append("        commandFile.close();")
        jsx.append("        commandFile.remove();")
        jsx.append("        ")
        jsx.append("        try {")
        jsx.append("            var cmd = eval('(' + cmdText + ')');")
        jsx.append("            if (cmd.command == 'STOP') {")
        jsx.append("                running = false;")
        jsx.append("            } else if (cmd.command == 'EXECUTE') {")
        jsx.append("                executeCommand(cmd);")
        jsx.append("            }")
        jsx.append("        } catch(e) {")
        jsx.append("            $.writeln('Error parsing command: ' + e.message);")
        jsx.append("        }")
        jsx.append("    }")
        jsx.append("}")
        jsx.append("")
        
        jsx.append("// Main loop")
        jsx.append("while (running) {")
        jsx.append("    updateHeartbeat();")
        jsx.append("    checkCommand();")
        jsx.append("    $.sleep(500);")
        jsx.append("}")
        jsx.append("")
        jsx.append("// Cleanup")
        jsx.append("if (heartbeatFile.exists) heartbeatFile.remove();")
        
        jsx_code = "\n".join(jsx)
        
        with open(self.resident_jsx, 'w', encoding='utf-8') as f:
            f.write(jsx_code)
        
        print(f"Generated resident JSX: {self.resident_jsx}")
        return self.resident_jsx
    
    def send_command(self, preset_id, source_files, output_path, config, is_single_run_with_file=False):
        """Send command to resident script"""
        preset_steps = self.db.get_preset_steps(preset_id)
        
        is_batch = len(source_files) > 0 and not is_single_run_with_file
        
        # Build steps array
        steps = []
        for step in preset_steps:
            action_detail = self.db.get_action_by_id(step['action_id'])
            if action_detail:
                action_type = action_detail.get('type', 'Action')
                
                step_data = {
                    'name': action_detail['name'],
                    'type': action_type
                }
                
                if action_type == 'Action':
                    step_data['action_set'] = step['action_set']
                elif action_type == 'Delay':
                    step_data['delay'] = action_detail.get('delay', 0)
                elif action_type == 'Script':
                    step_data['code'] = action_detail.get('javascript_code', '')
                    step_data['delay'] = action_detail.get('delay', 0)
                elif action_type == 'Export':
                    step_data['export_format'] = action_detail.get('export_format', 'PNG')
                
                steps.append(step_data)
        
        # Build command
        command = {
            'command': 'EXECUTE',
            'preset_id': preset_id,
            'files': [f.replace('\\', '/') for f in source_files],
            'output_path': output_path.replace('\\', '/'),
            'config': config,
            'steps': steps,
            'is_batch': is_batch,
            'is_single_run_with_file': is_single_run_with_file
        }
        
        # Write command file
        with open(self.command_file, 'w', encoding='utf-8') as f:
            json.dump(command, f, indent=2)
        
        print(f"Command sent to resident script")
        return self.command_file
    
    def generate_jsx(self, preset_id, source_files, output_path, config, is_single_run_with_file=False):
        """Generate JSX file for Illustrator - Use resident if available
        
        Args:
            preset_id: ID preset from database
            source_files: List of file paths to process (can be empty for single run)
            output_path: Output folder path
            config: Config dict (prefix, suffix, etc)
            is_single_run_with_file: True if single run mode with loaded file
        
        Returns:
            tuple: (jsx_path, is_resident) - path to JSX and whether using resident
        """
        # Check if resident is alive
        if self.is_resident_alive():
            print("Resident script detected - sending command")
            self.send_command(preset_id, source_files, output_path, config, is_single_run_with_file)
            return (None, True)  # No JSX file needed, using resident
        
        # Generate resident script if not exists or outdated
        print("Resident script not detected - generating new resident JSX")
        resident_path = self.generate_resident_jsx()
        
        # Send initial command
        self.send_command(preset_id, source_files, output_path, config, is_single_run_with_file)
        
        return (resident_path, False)  # Return resident JSX to launch
