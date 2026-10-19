import 'dart:io';
import 'dart:ui' as ui;


import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> captureUiAuditScreenshot(
  WidgetTester tester,
  String filename,
) async {
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('ui-audit-capture')),
  );
  final image = await boundary.toImage(pixelRatio: 1);
  try {
    final png = await image.toByteData(format: ui.ImageByteFormat.png);
    if (png == null) {
      throw StateError('Could not encode UI audit screenshot: $filename');
    }
    final directory = Directory('build/ui-audit');
    await directory.create(recursive: true);
    final safeName = filename.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
    await File('${directory.path}/$safeName.png').writeAsBytes(
      png.buffer.asUint8List(png.offsetInBytes, png.lengthInBytes),
      flush: true,
    );
  } finally {
    image.dispose();
  }
}
